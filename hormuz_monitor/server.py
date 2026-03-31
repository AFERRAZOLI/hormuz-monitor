"""
FastAPI server for the Hormuz Crisis Monitor.

Single endpoint GET / returns a fully rendered HTML dashboard
with live data from all sources. Responses are cached for
CACHE_TTL seconds (default 5 min) to avoid hammering APIs.
"""

import logging
import time
from datetime import date

import pandas as pd
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import CACHE_TTL_SECONDS, BRENT_TICKER, DUBAI_TICKER, PORTWATCH_URL
from .charts import generate_all_charts
from .dashboard import generate_html
from .fetchers import (
    _fetch_hormuz_tracker,
    fetch_brent_price,
    fetch_dubai_physical,
    fetch_hormuz_ship_count,
    fetch_insurance_premium,
)
from .signals import assess_cliff, assess_insurance, assess_ship_count, assess_spread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hormuz Crisis Monitor")

_cache: dict = {"html": None, "ts": 0}


def _fetch_history_from_apis() -> pd.DataFrame:
    """
    Build a YTD history DataFrame directly from APIs (no local CSV).
    Fetches: Brent + Dubai from yfinance, ships from PortWatch.
    """
    from datetime import datetime

    rows = {}

    # Brent + Dubai from yfinance
    try:
        import yfinance as yf

        for ticker, col in [(BRENT_TICKER, "brent"), (DUBAI_TICKER, "dubai_physical")]:
            hist = yf.Ticker(ticker).history(start="2026-01-01")
            for dt, row in hist.iterrows():
                d = dt.strftime("%Y-%m-%d")
                if d not in rows:
                    rows[d] = {}
                rows[d][col] = round(float(row["Close"]), 2)
    except Exception as e:
        logger.warning(f"yfinance history fetch failed: {e}")

    # Ship count from PortWatch
    try:
        params = {
            "where": "portid='chokepoint6' AND date >= timestamp '2026-01-01'",
            "outFields": "date,n_total",
            "orderByFields": "date ASC",
            "resultRecordCount": 500,
            "f": "json",
        }
        resp = requests.get(PORTWATCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        for f in resp.json().get("features", []):
            a = f["attributes"]
            d = datetime.utcfromtimestamp(a["date"] / 1000).strftime("%Y-%m-%d")
            if d not in rows:
                rows[d] = {}
            rows[d]["ship_count"] = a["n_total"]
    except Exception as e:
        logger.warning(f"PortWatch history fetch failed: {e}")

    if not rows:
        return pd.DataFrame()

    # Insurance premium milestones from news reports:
    # S&P Global, Caixin, Al Jazeera, Modern Diplomacy, HormuzTracker API
    _INSURANCE_MILESTONES = {
        "2026-01-02": 0.125,
        "2026-02-27": 0.125,
        "2026-02-28": 0.40,
        "2026-03-01": 0.625,
        "2026-03-02": 1.00,
        "2026-03-05": 1.50,
        "2026-03-07": 2.00,
        "2026-03-09": 3.50,
        "2026-03-13": 5.00,
        "2026-03-20": 4.00,
        "2026-03-25": 2.50,
    }
    # Add current value from HormuzTracker if available
    current_ins = fetch_insurance_premium()
    if current_ins is not None:
        _INSURANCE_MILESTONES[date.today().isoformat()] = current_ins

    # Cliff target (latest cliff event date)
    from .config import CLIFF_EVENTS
    cliff_target = max((d for d, _ in CLIFF_EVENTS), default=date.today())

    # Build DataFrame
    all_dates = sorted(rows.keys())
    records = []
    for d in all_dates:
        r = rows[d]
        brt = r.get("brent")
        dub = r.get("dubai_physical")
        spread = round(dub - brt, 2) if (brt and dub) else None
        d_date = date.fromisoformat(d)
        records.append({
            "date": d,
            "insurance_pct": None,
            "ship_count": r.get("ship_count"),
            "brent": brt,
            "dubai_physical": dub,
            "spread": spread,
            "cliff_days": (cliff_target - d_date).days,
            "notes": "",
        })

    # Interpolate insurance from milestones
    import numpy as np
    ins_series = pd.Series(_INSURANCE_MILESTONES, dtype=float)
    ins_series.index = pd.to_datetime(ins_series.index)

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])

    # Interpolate insurance premium across all dates
    interpolated = ins_series.reindex(df["date"]).interpolate(method="linear")
    df["insurance_pct"] = interpolated.values

    logger.info(f"Built history: {len(df)} days from APIs")
    return df


def _build_dashboard() -> str:
    """Fetch all data, assess signals, generate full HTML dashboard."""
    today = date.today()

    # Fetch live data
    brent = fetch_brent_price()
    dubai = fetch_dubai_physical()
    ships = fetch_hormuz_ship_count()
    insurance = fetch_insurance_premium()

    # Assess signals
    signals = [
        assess_insurance(insurance),
        assess_ship_count(ships),
        assess_spread(brent, dubai),
        assess_cliff(today),
    ]

    # Build history from APIs for charts
    history = _fetch_history_from_apis()

    # Generate charts
    charts = {}
    if not history.empty:
        try:
            charts = generate_all_charts(history)
        except Exception as e:
            logger.warning(f"Chart generation failed: {e}")

    # Fetch full HormuzTracker data for extended sections
    tracker_data = _fetch_hormuz_tracker()

    # Build HTML
    html = generate_html(
        signals,
        history=history,
        as_of=today,
        charts=charts,
        tracker_data=tracker_data,
    )
    return html


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the live Hormuz Crisis Monitor dashboard."""
    now = time.time()

    if _cache["html"] and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
        logger.info("Serving cached dashboard")
        return _cache["html"]

    logger.info("Building fresh dashboard...")
    html = _build_dashboard()
    _cache["html"] = html
    _cache["ts"] = now
    return html


@app.get("/health")
def health():
    """Health check for Railway."""
    return {"status": "ok", "cache_age": int(time.time() - _cache["ts"])}
