"""
Central configuration for the Hormuz Monitor.

All values have sensible defaults but can be overridden via environment
variables for deployment flexibility.
"""

import json
import os
from datetime import date


# ── API sources ──────────────────────────────────────────────────────

HORMUZ_TRACKER_URL = os.getenv(
    "HORMUZ_TRACKER_URL", "https://www.hormuztracker.com/api/data"
)
PORTWATCH_URL = os.getenv(
    "PORTWATCH_URL",
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
    "/Daily_Chokepoints_Data/FeatureServer/0/query",
)
BRENT_TICKER = os.getenv("BRENT_TICKER", "BZ=F")
DUBAI_TICKER = os.getenv("DUBAI_TICKER", "DCB=F")


# ── Signal thresholds ────────────────────────────────────────────────
# Each list defines [green/amber, amber/red, red/critical] boundaries.

INSURANCE_THRESHOLDS = json.loads(
    os.getenv("INSURANCE_THRESHOLDS", "[1.0, 2.0, 5.0]")
)
SHIP_THRESHOLDS = json.loads(
    os.getenv("SHIP_THRESHOLDS", "[10, 30, 60]")
)
SPREAD_THRESHOLDS = json.loads(
    os.getenv("SPREAD_THRESHOLDS", "[3, 7, 12]")
)
CLIFF_THRESHOLDS = json.loads(
    os.getenv("CLIFF_THRESHOLDS", "[7, 14, 30]")
)

# ── Pre-crisis baselines (display only) ──────────────────────────────

INSURANCE_BASELINE = os.getenv("INSURANCE_BASELINE", "0.25%")
SHIP_BASELINE = os.getenv("SHIP_BASELINE", "100+")
SPREAD_BASELINE = os.getenv("SPREAD_BASELINE", "+/-$2")


# ── Cliff events ─────────────────────────────────────────────────────
# JSON array of [date_iso, description] pairs, or use defaults.

_DEFAULT_CLIFF_EVENTS = [
    ["2026-04-01", "Formosa Plastics force majeure begins"],
    ["2026-04-15", "US SPR 400M bbl release runs dry (est.)"],
    ["2026-04-15", "US waiver for India-Russia crude expires (est.)"],
]

_cliff_json = os.getenv("CLIFF_EVENTS")
_cliff_raw = json.loads(_cliff_json) if _cliff_json else _DEFAULT_CLIFF_EVENTS

CLIFF_EVENTS: list[tuple[date, str]] = [
    (date.fromisoformat(d), desc) for d, desc in _cliff_raw
]


# ── Cache TTL for server mode ────────────────────────────────────────

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", "300"))
