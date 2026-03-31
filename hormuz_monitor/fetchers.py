"""
Auto-fetchers for data that can be pulled programmatically.

- Brent crude: yfinance (BZ=F)
- Dubai crude (Platts): yfinance (DCB=F)
- Ship crossings: HormuzTracker API (primary) + IMF PortWatch (fallback)
- Insurance premium: HormuzTracker API (parsed from premium range)
"""

import logging
import re

import requests

from .config import BRENT_TICKER, DUBAI_TICKER, HORMUZ_TRACKER_URL, PORTWATCH_URL

logger = logging.getLogger(__name__)


def fetch_brent_price() -> float | None:
    """Fetch latest Brent crude front-month price via yfinance."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(BRENT_TICKER)
        hist = ticker.history(period="5d")
        if hist.empty:
            logger.warning("No Brent data from yfinance")
            return None
        price = float(hist["Close"].iloc[-1])
        logger.info(f"Brent crude: ${price:.2f}")
        return price
    except Exception as e:
        logger.warning(f"Failed to fetch Brent: {e}")
        return None


def fetch_dubai_physical() -> float | None:
    """
    Fetch Dubai crude (Platts) futures price via yfinance.

    Ticker DCB=F is the CME Dubai Crude Oil (Platts) Financial Futures
    front-month contract. Highly correlated with Dubai physical spot.
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(DUBAI_TICKER)
        hist = ticker.history(period="5d")
        if hist.empty:
            logger.warning("No Dubai crude data from yfinance")
            return None
        price = float(hist["Close"].iloc[-1])
        logger.info(f"Dubai crude (DCB=F): ${price:.2f}")
        return price
    except Exception as e:
        logger.warning(f"Failed to fetch Dubai crude: {e}")
        return None


# ── HormuzTracker API ────────────────────────────────────────────────

_hormuz_tracker_cache: dict | None = None


def _fetch_hormuz_tracker() -> dict | None:
    """Fetch the full HormuzTracker JSON. Cached for the process lifetime."""
    global _hormuz_tracker_cache
    if _hormuz_tracker_cache is not None:
        return _hormuz_tracker_cache
    try:
        resp = requests.get(HORMUZ_TRACKER_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            f"HormuzTracker API: day {data['meta']['day']}, "
            f"updated {data['meta']['updated']}"
        )
        _hormuz_tracker_cache = data
        return data
    except Exception as e:
        logger.warning(f"HormuzTracker API failed: {e}")
        return None


def fetch_hormuz_ship_count() -> float | None:
    """
    Fetch latest daily ship transit count through Hormuz.

    Primary: HormuzTracker API (daily, curated from S&P/Kpler/MarineTraffic).
    Fallback: IMF PortWatch ArcGIS (weekly).
    """
    # Try HormuzTracker first
    data = _fetch_hormuz_tracker()
    if data:
        ship_data = data.get("crisis", {}).get("shipCount", {})
        count = ship_data.get("current")
        if count is not None:
            baseline = ship_data.get("baseline", "?")
            drop = ship_data.get("dropPercent", "?")
            verified = ship_data.get("lastVerified", "unknown")
            logger.info(
                f"Hormuz ships (HormuzTracker): {count}/day "
                f"(baseline {baseline}, -{drop}%, verified {verified})"
            )
            return float(count)

    # Fallback to PortWatch
    return _fetch_portwatch_ships()


def fetch_insurance_premium() -> float | None:
    """
    Fetch war-risk insurance premium from HormuzTracker API.

    Parses the premium range string (e.g. "0.5% - 2.0%+") and returns
    the midpoint as a percentage. Returns None if unavailable.
    """
    data = _fetch_hormuz_tracker()
    if not data:
        return None

    premiums = data.get("insurance", {}).get("premiums", {})
    current_str = premiums.get("current", "")

    # Parse percentage values from strings like "0.5% – 2.0%+"
    numbers = re.findall(r"(\d+\.?\d*)\s*%", current_str)
    if not numbers:
        logger.info(f"Could not parse insurance premium from: '{current_str}'")
        return None

    values = [float(n) for n in numbers]
    # Use the max of the range (conservative — what you'd actually pay)
    premium = max(values)
    logger.info(
        f"War-risk insurance (HormuzTracker): {premium:.2f}% "
        f"(range: {current_str})"
    )
    return premium


# ── PortWatch fallback ───────────────────────────────────────────────

def _fetch_portwatch_ships() -> float | None:
    """Fallback: fetch ship count from IMF PortWatch ArcGIS."""
    params = {
        "where": "portid='chokepoint6'",
        "outFields": "date,n_total,n_tanker",
        "orderByFields": "date DESC",
        "resultRecordCount": 1,
        "f": "json",
    }
    try:
        resp = requests.get(PORTWATCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            logger.info("PortWatch returned no Hormuz data")
            return None

        attrs = features[0].get("attributes", {})
        count = attrs.get("n_total")
        tankers = attrs.get("n_tanker", 0)
        if count is None:
            return None

        from datetime import datetime
        date_ms = attrs.get("date")
        date_str = (
            datetime.utcfromtimestamp(date_ms / 1000).strftime("%Y-%m-%d")
            if date_ms else "unknown"
        )

        count = float(count)
        logger.info(
            f"Hormuz ships (PortWatch fallback): {count:.0f} total, "
            f"{tankers} tankers (date: {date_str})"
        )
        return count
    except Exception as e:
        logger.warning(f"PortWatch fallback failed: {e}")
        return None
