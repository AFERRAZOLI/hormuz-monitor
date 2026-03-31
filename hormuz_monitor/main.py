"""
Hormuz Crisis Monitor — CLI entry point.

Usage:
    # Auto-fetch Brent + show dashboard (prompts for manual inputs):
    python -m hormuz_monitor.main

    # Supply all values directly (no prompts):
    python -m hormuz_monitor.main --insurance 5.2 --ships 8 --dubai 126

    # Just show the last readings without updating:
    python -m hormuz_monitor.main --view

    # Generate HTML report:
    python -m hormuz_monitor.main --html
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .config import CLIFF_EVENTS
from .charts import generate_all_charts
from .dashboard import generate_html, print_dashboard, print_trend
from .data_store import DEFAULT_PATH, append_reading, load_history
from .fetchers import (
    _fetch_hormuz_tracker,
    fetch_brent_price,
    fetch_dubai_physical,
    fetch_hormuz_ship_count,
    fetch_insurance_premium,
)
from .signals import assess_cliff, assess_insurance, assess_ship_count, assess_spread

logger = logging.getLogger(__name__)


def _prompt(label: str, current: float | None = None) -> float | None:
    """Prompt user for a value, with option to skip."""
    hint = f" [{current}]" if current is not None else ""
    try:
        raw = input(f"  {label}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return current
    if not raw:
        return current
    try:
        return float(raw)
    except ValueError:
        print(f"    Invalid number, using {'previous' if current else 'None'}")
        return current


def run(
    insurance_pct: float | None = None,
    ship_count: float | None = None,
    dubai_physical: float | None = None,
    brent_override: float | None = None,
    interactive: bool = True,
    save: bool = True,
    output_html: bool = False,
    view_only: bool = False,
    output_dir: Path | None = None,
    history_path: Path | None = None,
) -> list:
    """Run the monitor: fetch, assess, display, store."""
    today = date.today()
    hist_path = history_path or DEFAULT_PATH
    output_dir = output_dir or Path("output")

    # ── View-only mode ──
    if view_only:
        history = load_history(hist_path)
        print_trend(history)
        return []

    # ── Auto-fetch what we can ──
    brent = brent_override or fetch_brent_price()

    if dubai_physical is None:
        dubai_physical = fetch_dubai_physical()

    if ship_count is None:
        ship_count = fetch_hormuz_ship_count()

    if insurance_pct is None:
        insurance_pct = fetch_insurance_premium()

    # ── Load previous values for defaults ──
    from .data_store import get_latest

    prev = get_latest(hist_path) or {}
    prev_ins = prev.get("insurance_pct")
    prev_ships = prev.get("ship_count")
    prev_dubai = prev.get("dubai_physical")

    # ── Interactive prompts for data we couldn't auto-fetch ──
    if interactive and insurance_pct is None:
        print("\n  Manual inputs (Enter to keep previous, blank to skip):")
        insurance_pct = _prompt(
            "War-risk insurance (% hull)", insurance_pct or prev_ins
        )
    elif insurance_pct is None:
        insurance_pct = prev_ins

    if interactive and ship_count is None:
        ship_count = _prompt("Daily ship crossings", ship_count or prev_ships)
    elif ship_count is None:
        ship_count = prev_ships

    if interactive and dubai_physical is None:
        dubai_physical = _prompt("Dubai physical ($/bbl)", dubai_physical or prev_dubai)
    elif dubai_physical is None:
        dubai_physical = prev_dubai

    # ── Assess signals ──
    signals = [
        assess_insurance(insurance_pct),
        assess_ship_count(ship_count),
        assess_spread(brent, dubai_physical),
        assess_cliff(today),
    ]

    # ── Display ──
    print_dashboard(signals, as_of=today)

    history = load_history(hist_path)
    print_trend(history)

    # ── Store reading ──
    spread = None
    if brent is not None and dubai_physical is not None:
        spread = round(dubai_physical - brent, 2)

    if save:
        append_reading(
            hist_path,
            as_of=today,
            insurance_pct=insurance_pct,
            ship_count=ship_count,
            brent=brent,
            dubai_physical=dubai_physical,
            spread=spread,
            cliff_days=(max((d for d, _ in CLIFF_EVENTS), default=today) - today).days,
        )
        print(f"  Reading saved to {hist_path}")

    # ── HTML output ──
    if output_html:
        # Reload history after saving so chart includes today's reading
        history = load_history(hist_path)
        charts = generate_all_charts(history)
        tracker_data = _fetch_hormuz_tracker()
        html = generate_html(signals, history, as_of=today, charts=charts, tracker_data=tracker_data)
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_dir / f"hormuz_monitor_{today.isoformat()}.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"  HTML report: {html_path}")

    return signals


def main():
    parser = argparse.ArgumentParser(
        description="Hormuz Crisis Monitor — 4 signals for India crude exposure"
    )
    parser.add_argument("--insurance", type=float, help="War-risk insurance (%% hull)")
    parser.add_argument("--ships", type=float, help="Daily ship crossings (AIS count)")
    parser.add_argument("--dubai", type=float, help="Dubai physical price ($/bbl)")
    parser.add_argument("--brent", type=float, help="Override Brent price ($/bbl)")
    parser.add_argument("--view", action="store_true", help="View history only")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--no-save", action="store_true", help="Don't save this reading")
    parser.add_argument("--no-prompt", action="store_true", help="Non-interactive mode")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    parser.add_argument("--history", type=str, help="Path to history CSV")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    run(
        insurance_pct=args.insurance,
        ship_count=args.ships,
        dubai_physical=args.dubai,
        brent_override=args.brent,
        interactive=not args.no_prompt,
        save=not args.no_save,
        output_html=args.html,
        view_only=args.view,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        history_path=Path(args.history) if args.history else None,
    )


if __name__ == "__main__":
    main()
