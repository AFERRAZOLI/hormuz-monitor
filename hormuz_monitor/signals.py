"""
Signal definitions and threshold logic for the Hormuz monitor.

Four signals:
1. War-risk insurance premium (% of hull value)
2. Daily ship crossings through Hormuz (AIS count)
3. Brent-Dubai physical spread ($/bbl)
4. Days until mid-April cliff (SPR depletion / waiver expiry)
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .config import (
    CLIFF_EVENTS,
    CLIFF_THRESHOLDS,
    INSURANCE_BASELINE,
    INSURANCE_THRESHOLDS,
    SHIP_BASELINE,
    SHIP_THRESHOLDS,
    SPREAD_BASELINE,
    SPREAD_THRESHOLDS,
)


class Level(Enum):
    """Traffic-light severity for each signal."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    CRITICAL = "CRITICAL"


@dataclass
class Signal:
    name: str
    value: float | None
    unit: str
    level: Level
    context: str
    pre_crisis: str


# ── 1. Insurance premium ────────────────────────────────────────────
def assess_insurance(premium_pct: float | None) -> Signal:
    if premium_pct is None:
        return Signal(
            "War-Risk Insurance", None, "% hull", Level.RED,
            "No data -- assume elevated risk", INSURANCE_BASELINE,
        )

    t = INSURANCE_THRESHOLDS  # [green/amber, amber/red, red/critical]
    if premium_pct < t[0]:
        level, ctx = Level.GREEN, "Underwriters pricing near-normal risk"
    elif premium_pct < t[1]:
        level, ctx = Level.AMBER, "Declining -- reopening being priced in"
    elif premium_pct < t[2]:
        level, ctx = Level.RED, "Still elevated -- passage risky"
    else:
        level, ctx = Level.CRITICAL, "Near-prohibitive -- effective blockade"

    return Signal("War-Risk Insurance", premium_pct, "% hull", level, ctx, INSURANCE_BASELINE)


# ── 2. Ship crossings ───────────────────────────────────────────────
def assess_ship_count(daily_count: float | None) -> Signal:
    if daily_count is None:
        return Signal(
            "Hormuz Ship Crossings", None, "ships/day", Level.RED,
            "No data -- assume blockade continues", SHIP_BASELINE,
        )

    t = SHIP_THRESHOLDS  # [critical/red, red/amber, amber/green]
    if daily_count > t[2]:
        level, ctx = Level.GREEN, "Trade substantially resumed"
    elif daily_count > t[1]:
        level, ctx = Level.AMBER, "Partial reopening -- selective passage"
    elif daily_count >= t[0]:
        level, ctx = Level.RED, "Trickle -- mostly China/India exemptions"
    else:
        level, ctx = Level.CRITICAL, "Near-total blockade"

    return Signal("Hormuz Ship Crossings", daily_count, "ships/day", level, ctx, SHIP_BASELINE)


# ── 3. Brent-Dubai spread ───────────────────────────────────────────
def assess_spread(brent: float | None, dubai_physical: float | None) -> Signal:
    if brent is None or dubai_physical is None:
        return Signal(
            "Brent-Dubai Spread", None, "$/bbl", Level.AMBER,
            "Incomplete data", SPREAD_BASELINE,
        )

    spread = dubai_physical - brent
    t = SPREAD_THRESHOLDS  # [green/amber, amber/red, red/critical]

    if abs(spread) < t[0]:
        level, ctx = Level.GREEN, "Paper and physical aligned"
    elif abs(spread) < t[1]:
        level, ctx = Level.AMBER, f"Moderate dislocation (Dubai {'above' if spread > 0 else 'below'} Brent)"
    elif abs(spread) < t[2]:
        level, ctx = Level.RED, "Significant physical premium -- jawboning distortion"
    else:
        level, ctx = Level.CRITICAL, "Extreme dislocation -- paper price unreliable for India oil bill"

    return Signal("Brent-Dubai Spread", round(spread, 2), "$/bbl", level, ctx, SPREAD_BASELINE)


# ── 4. Cliff countdown ──────────────────────────────────────────────
def assess_cliff(as_of: date | None = None) -> Signal:
    as_of = as_of or date.today()
    upcoming = [(d, desc) for d, desc in CLIFF_EVENTS if d >= as_of]

    if not upcoming:
        return Signal(
            "April Cliff", 0, "days", Level.CRITICAL,
            "All cliff events have passed -- check if stopgaps were extended",
            "Multiple measures expire mid-April",
        )

    nearest_date, nearest_desc = min(upcoming, key=lambda x: x[0])
    days_left = (nearest_date - as_of).days

    t = CLIFF_THRESHOLDS  # [critical/red, red/amber, amber/green]
    if days_left > t[2]:
        level = Level.GREEN
    elif days_left > t[1]:
        level = Level.AMBER
    elif days_left > t[0]:
        level = Level.RED
    else:
        level = Level.CRITICAL

    ctx = f"{days_left}d to: {nearest_desc}"
    return Signal("April Cliff", days_left, "days", level, ctx, "Multiple measures expire mid-April")
