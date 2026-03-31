"""
FastAPI server for the Hormuz Crisis Monitor.

Single endpoint GET / returns a fully rendered HTML dashboard
with live data from all sources. Responses are cached for
CACHE_TTL seconds (default 5 min) to avoid hammering APIs.
"""

import logging
import time
from datetime import date

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import CACHE_TTL_SECONDS
from .charts import generate_all_charts
from .dashboard import generate_html
from .data_store import load_history, DEFAULT_PATH
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

    # Load history for charts (if CSV exists)
    try:
        history = load_history(DEFAULT_PATH)
    except Exception:
        history = None

    # Generate charts from history
    charts = {}
    if history is not None and not history.empty:
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
