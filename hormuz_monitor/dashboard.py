"""
Console + HTML dashboard for the Hormuz monitor.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from .signals import Level, Signal


# ── ANSI colors for console ──────────────────────────────────────────
_COLORS = {
    Level.GREEN: "\033[92m",
    Level.AMBER: "\033[93m",
    Level.RED: "\033[91m",
    Level.CRITICAL: "\033[95m",
}
_RESET = "\033[0m"


def _bar(level: Level) -> str:
    blocks = {Level.GREEN: 1, Level.AMBER: 2, Level.RED: 3, Level.CRITICAL: 4}
    n = blocks[level]
    return _COLORS[level] + "#" * n + "." * (4 - n) + _RESET


def print_dashboard(signals: list[Signal], as_of: date | None = None) -> None:
    """Print a compact console dashboard."""
    as_of = as_of or date.today()
    width = 72
    print()
    print("=" * width)
    print(f"  HORMUZ CRISIS MONITOR -- {as_of.strftime('%B %d, %Y')}")
    print("=" * width)

    for s in signals:
        val_str = f"{s.value}" if s.value is not None else "N/A"
        if isinstance(s.value, float):
            val_str = f"{s.value:.2f}"
        elif isinstance(s.value, int):
            val_str = str(s.value)

        color = _COLORS[s.level]
        print(
            f"\n  {_bar(s.level)} {color}{s.level.value:8s}{_RESET}  "
            f"{s.name}"
        )
        print(f"           Value: {val_str} {s.unit}  (pre-crisis: {s.pre_crisis})")
        print(f"           {s.context}")

    print()
    print("-" * width)
    print("  Sources: Lloyd's List (insurance) | MarineTraffic/WTO (AIS)")
    print("           Platts/Argus (Dubai phys) | yfinance (Brent)")
    print("=" * width)
    print()


def print_trend(history: pd.DataFrame, last_n: int = 7) -> None:
    """Print a mini trend table from the last N readings."""
    if history.empty:
        print("  No historical data yet.\n")
        return

    df = history.tail(last_n).copy()
    print(f"\n  RECENT READINGS (last {len(df)}):")
    print(f"  {'Date':<12} {'Ins %':>7} {'Ships':>6} {'Brent':>7} {'Dubai':>7} {'Spread':>7}")
    print("  " + "-" * 50)
    for _, row in df.iterrows():
        d = row["date"]
        if isinstance(d, pd.Timestamp):
            d = d.strftime("%Y-%m-%d")
        ins = f"{row['insurance_pct']:.2f}" if pd.notna(row.get("insurance_pct")) else "  -"
        shp = f"{row['ship_count']:.0f}" if pd.notna(row.get("ship_count")) else "  -"
        brt = f"{row['brent']:.1f}" if pd.notna(row.get("brent")) else "  -"
        dub = f"{row['dubai_physical']:.1f}" if pd.notna(row.get("dubai_physical")) else "  -"
        spr = f"{row['spread']:.1f}" if pd.notna(row.get("spread")) else "  -"
        print(f"  {d:<12} {ins:>7} {shp:>6} {brt:>7} {dub:>7} {spr:>7}")
    print()


# ── HTML output ──────────────────────────────────────────────────────

_HTML_COLORS = {
    Level.GREEN: "#22c55e",
    Level.AMBER: "#eab308",
    Level.RED: "#ef4444",
    Level.CRITICAL: "#a855f7",
}


def generate_html(
    signals: list[Signal],
    history: pd.DataFrame | None = None,
    as_of: date | None = None,
    charts: dict[str, str] | None = None,
    tracker_data: dict | None = None,
) -> str:
    """Generate a self-contained HTML dashboard with embedded charts."""
    as_of = as_of or date.today()

    signal_rows = ""
    for s in signals:
        color = _HTML_COLORS[s.level]
        val = f"{s.value:.2f}" if isinstance(s.value, float) else (str(s.value) if s.value is not None else "N/A")
        signal_rows += f"""
        <tr>
          <td style="border-left:4px solid {color};padding-left:8px">
            <strong>{s.name}</strong><br>
            <small style="color:#888">Pre-crisis: {s.pre_crisis}</small>
          </td>
          <td style="text-align:right;font-size:1.3em;font-weight:bold">{val} <small>{s.unit}</small></td>
          <td><span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.85em">{s.level.value}</span></td>
          <td style="color:#555;font-size:0.9em">{s.context}</td>
        </tr>"""

    history_section = ""
    if history is not None and not history.empty:
        last = history.tail(10)
        hist_rows = ""
        for _, row in last.iterrows():
            d = row["date"]
            if isinstance(d, pd.Timestamp):
                d = d.strftime("%Y-%m-%d")
            fmt = lambda v, dec=1: f"{v:.{dec}f}" if pd.notna(v) else "-"
            hist_rows += f"""
            <tr>
              <td>{d}</td>
              <td>{fmt(row.get('insurance_pct'), 2)}</td>
              <td>{fmt(row.get('ship_count'), 0)}</td>
              <td>{fmt(row.get('brent'))}</td>
              <td>{fmt(row.get('dubai_physical'))}</td>
              <td>{fmt(row.get('spread'))}</td>
            </tr>"""

        history_section = f"""
        <h2 style="margin-top:2em">Trend</h2>
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:2px solid #333;text-align:right">
              <th style="text-align:left">Date</th>
              <th>Insurance %*</th>
              <th>Ships</th>
              <th>Brent</th>
              <th>Dubai Phys</th>
              <th>Spread</th>
            </tr>
          </thead>
          <tbody>{hist_rows}</tbody>
        </table>
        <p style="font-size:.75em;color:#999">*Insurance values are interpolated from news-reported milestones (S&amp;P Global, Caixin, Al Jazeera). Not direct market data.</p>"""

    return _render_html(as_of, signal_rows, history_section, charts, tracker_data)


def _build_charts_section(charts: dict[str, str] | None) -> str:
    if not charts:
        return ""

    titles = {
        "insurance": "War-Risk Insurance Premium",
        "ships": "Hormuz Ship Crossings",
        "oil_spread": "Paper vs Physical Crude",
        "cliff": "April Cliff Countdown",
    }
    html = '<h2 style="margin-top:2em">Historical Charts</h2>\n'
    for key in ["insurance", "ships", "oil_spread", "cliff"]:
        if key in charts:
            html += f"""
            <div style="margin-bottom:1.5em">
              <img src="data:image/png;base64,{charts[key]}"
                   style="width:100%;max-width:1050px" alt="{titles.get(key, key)}">
            </div>"""
    return html


def _build_severity_section(crisis: dict) -> str:
    """Severity score gauge + factor breakdown."""
    score = crisis.get("severityScore", 0)
    factors = crisis.get("severityFactors", {})
    status = crisis.get("statusDescription", "")
    day = crisis.get("timeline", [{}])
    start = crisis.get("startDate", "?")

    factor_rows = ""
    for key, f in factors.items():
        s = f.get("score", 0)
        color = "#ef4444" if s >= 8 else "#eab308" if s >= 5 else "#22c55e"
        bar_w = s * 10
        factor_rows += f"""
        <tr>
          <td>{f.get('label','')}</td>
          <td style="text-align:center"><strong>{s}/10</strong></td>
          <td style="width:40%">
            <div style="background:#eee;border-radius:4px;height:14px">
              <div style="background:{color};width:{bar_w}%;height:100%;border-radius:4px"></div>
            </div>
          </td>
          <td style="font-size:.85em;color:#555">{f.get('detail','')[:120]}</td>
        </tr>"""

    return f"""
    <h2>Crisis Severity: {score}/10</h2>
    <p style="color:#666">Day {len(crisis.get('timeline',[]))} since {start}. {status[:200]}</p>
    <table><thead>
      <tr style="border-bottom:2px solid #333"><th style="text-align:left">Factor</th><th>Score</th><th>Level</th><th style="text-align:left">Detail</th></tr>
    </thead><tbody>{factor_rows}</tbody></table>"""


def _build_ships_section(crisis: dict) -> str:
    """Ship traffic + stranded vessels."""
    sc = crisis.get("shipCount", {})
    trapped = crisis.get("shipsTrapped", {})

    return f"""
    <h2>Ship Traffic</h2>
    <div style="display:flex;gap:2em;flex-wrap:wrap;margin-bottom:1em">
      <div style="text-align:center;padding:1em;background:#fef2f2;border-radius:8px;flex:1;min-width:150px">
        <div style="font-size:2.5em;font-weight:bold;color:#ef4444">{sc.get('current','?')}</div>
        <div style="color:#666">ships/day</div>
        <div style="font-size:.8em;color:#999">baseline: {sc.get('baseline','?')}</div>
      </div>
      <div style="text-align:center;padding:1em;background:#fef2f2;border-radius:8px;flex:1;min-width:150px">
        <div style="font-size:2.5em;font-weight:bold;color:#ef4444">-{sc.get('dropPercent','?')}%</div>
        <div style="color:#666">traffic drop</div>
      </div>
      <div style="text-align:center;padding:1em;background:#fefce8;border-radius:8px;flex:1;min-width:150px">
        <div style="font-size:2.5em;font-weight:bold;color:#b45309">{trapped.get('insideGulf',0)+trapped.get('waitingOutside',0):,}</div>
        <div style="color:#666">ships stranded</div>
        <div style="font-size:.8em;color:#999">{trapped.get('insideGulf',0):,} inside Gulf, {trapped.get('waitingOutside',0):,} outside</div>
      </div>
      <div style="text-align:center;padding:1em;background:#fefce8;border-radius:8px;flex:1;min-width:150px">
        <div style="font-size:2.5em;font-weight:bold;color:#b45309">{trapped.get('seafarersStranded',0):,}</div>
        <div style="color:#666">seafarers stranded</div>
      </div>
    </div>
    <p style="font-size:.85em;color:#888">{sc.get('note','')}</p>"""


def _build_insurance_section(ins: dict) -> str:
    """Insurance details with P&I club table."""
    premiums = ins.get("premiums", {})
    clubs = ins.get("clubs", [])

    club_rows = ""
    for c in clubs:
        scolor = "#ef4444" if c.get("status") == "cancelled" else "#eab308"
        club_rows += f"""
        <tr>
          <td>{c.get('name','')}</td>
          <td><span style="color:{scolor};font-weight:bold">{c.get('status','').upper()}</span></td>
          <td>{c.get('date','')}</td>
        </tr>"""

    return f"""
    <h2>Insurance</h2>
    <div style="display:flex;gap:2em;flex-wrap:wrap;margin-bottom:1em">
      <div style="flex:1;min-width:200px;padding:1em;background:#fef2f2;border-radius:8px">
        <div style="font-size:.85em;color:#666">Premium (before)</div>
        <div style="font-size:1.3em;font-weight:bold">{premiums.get('before','?')}</div>
        <div style="font-size:.85em;color:#666;margin-top:.5em">VLCC cost</div>
        <div>{premiums.get('vlccBefore','?')}</div>
      </div>
      <div style="flex:1;min-width:200px;padding:1em;background:#fef2f2;border-radius:8px;border:2px solid #ef4444">
        <div style="font-size:.85em;color:#666">Premium (now)</div>
        <div style="font-size:1.3em;font-weight:bold;color:#ef4444">{premiums.get('current','?')}</div>
        <div style="font-size:.85em;color:#666;margin-top:.5em">VLCC cost</div>
        <div style="color:#ef4444;font-weight:bold">{premiums.get('vlccCurrent','?')}</div>
      </div>
    </div>
    <p style="font-size:.9em;color:#555;background:#f9fafb;padding:1em;border-radius:8px;border-left:4px solid #ef4444">{ins.get('whyItMatters','')}</p>
    <table style="margin-top:1em"><thead>
      <tr style="border-bottom:2px solid #333"><th style="text-align:left">P&I Club</th><th>Status</th><th>Date</th></tr>
    </thead><tbody>{club_rows}</tbody></table>"""


def _build_carriers_section(carriers: list) -> str:
    """Carrier suspension table."""
    rows = ""
    for c in carriers:
        scolor = "#ef4444" if c.get("status") == "suspended" else "#eab308"
        rows += f"""
        <tr>
          <td><strong>{c.get('name','')}</strong></td>
          <td><span style="color:{scolor}">{c.get('status','').upper()}</span></td>
          <td style="text-align:right">{c.get('vesselTrapped') or '-'}</td>
          <td style="text-align:right">{f"{c['teuTrapped']:,}" if c.get('teuTrapped') else '-'}</td>
          <td style="font-size:.85em">{c.get('surcharge','')}</td>
        </tr>"""

    return f"""
    <h2>Carrier Status</h2>
    <table><thead>
      <tr style="border-bottom:2px solid #333">
        <th style="text-align:left">Carrier</th><th>Status</th>
        <th style="text-align:right">Vessels</th><th style="text-align:right">TEU</th>
        <th style="text-align:left">Surcharge</th>
      </tr>
    </thead><tbody>{rows}</tbody></table>"""


def _build_exposure_section(countries: list) -> str:
    """Country exposure table."""
    rows = ""
    for c in countries:
        dep = c.get("hormuzDependency", 0)
        bar_color = "#ef4444" if dep > 70 else "#eab308" if dep > 40 else "#22c55e"
        spr_days = c.get("sprDaysHormuz", "?")
        rows += f"""
        <tr>
          <td>{c.get('flag','')} <strong>{c.get('country','')}</strong></td>
          <td style="text-align:right">{dep}%</td>
          <td style="width:25%">
            <div style="background:#eee;border-radius:4px;height:14px">
              <div style="background:{bar_color};width:{dep}%;height:100%;border-radius:4px"></div>
            </div>
          </td>
          <td style="text-align:right">{c.get('oilFromHormuz','')}</td>
          <td style="text-align:right">{spr_days} days</td>
          <td style="font-size:.85em;color:#555">{c.get('notes','')[:80]}</td>
        </tr>"""

    return f"""
    <h2>Country Exposure</h2>
    <table><thead>
      <tr style="border-bottom:2px solid #333">
        <th style="text-align:left">Country</th><th>Hormuz Dep.</th><th>Level</th>
        <th style="text-align:right">Oil via Hormuz</th><th style="text-align:right">SPR Cover</th>
        <th style="text-align:left">Notes</th>
      </tr>
    </thead><tbody>{rows}</tbody></table>"""


def _build_routes_section(routes: list) -> str:
    """Reroute cost table."""
    rows = ""
    for r in routes:
        extra = r.get("capeDays", 0) - r.get("normalDays", 0)
        rows += f"""
        <tr>
          <td>{r.get('origin','')}</td>
          <td>{r.get('destination','')}</td>
          <td style="text-align:right">{r.get('normalDays','')}d</td>
          <td style="text-align:right">{r.get('capeDays','')}d</td>
          <td style="text-align:right;color:#ef4444">+{extra}d</td>
          <td style="text-align:right">${r.get('additionalCostUSD',0):,}</td>
          <td style="font-size:.85em">{r.get('vesselType','')}</td>
        </tr>"""

    return f"""
    <h2>Reroute via Cape of Good Hope</h2>
    <table><thead>
      <tr style="border-bottom:2px solid #333">
        <th style="text-align:left">Origin</th><th style="text-align:left">Dest</th>
        <th>Normal</th><th>Cape</th><th>Extra</th>
        <th style="text-align:right">Add. Cost</th><th>Vessel</th>
      </tr>
    </thead><tbody>{rows}</tbody></table>"""


def _build_consumer_section(items: list) -> str:
    """Consumer impact cards."""
    cards = ""
    for item in items:
        pct_lo = item.get("pctLow", 0)
        pct_hi = item.get("pctHigh", 0)
        cards += f"""
        <div style="flex:1;min-width:180px;padding:1em;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb">
          <div style="font-size:1.2em">{item.get('icon','')} <strong>{item.get('category','')}</strong></div>
          <div style="color:#ef4444;font-weight:bold;font-size:1.1em;margin:.3em 0">+{pct_lo}-{pct_hi}%</div>
          <div style="font-size:.8em;color:#666">{item.get('status','')}</div>
          <div style="font-size:.8em;color:#888;margin-top:.5em">{item.get('explanation','')[:120]}</div>
        </div>"""

    return f"""
    <h2>Consumer Impact</h2>
    <div style="display:flex;gap:1em;flex-wrap:wrap">{cards}</div>"""


def _build_timeline_section(timeline: list) -> str:
    """Crisis timeline."""
    rows = ""
    for e in timeline:
        tcolor = "#ef4444" if e.get("type") == "disruption" else "#3b82f6" if e.get("type") == "response" else "#22c55e"
        rows += f"""
        <tr>
          <td style="white-space:nowrap;border-left:3px solid {tcolor};padding-left:8px">
            <strong>Day {e.get('day','')}</strong><br>
            <span style="font-size:.8em;color:#888">{e.get('date','')}</span>
          </td>
          <td>{e.get('event','')}</td>
          <td style="font-size:.85em;color:#555">{e.get('impact','')}</td>
        </tr>"""

    return f"""
    <h2>Crisis Timeline</h2>
    <table><thead>
      <tr style="border-bottom:2px solid #333"><th style="text-align:left">Day</th><th style="text-align:left">Event</th><th style="text-align:left">Impact</th></tr>
    </thead><tbody>{rows}</tbody></table>"""


def _build_tracker_sections(data: dict | None) -> str:
    """Build all HormuzTracker data sections."""
    if not data:
        return ""

    sections = []
    crisis = data.get("crisis", {})
    if crisis:
        sections.append(_build_severity_section(crisis))
        sections.append(_build_ships_section(crisis))

    ins = data.get("insurance")
    if ins:
        sections.append(_build_insurance_section(ins))

    carriers = data.get("carriers")
    if carriers:
        sections.append(_build_carriers_section(carriers))

    countries = data.get("countryExposure")
    if countries:
        sections.append(_build_exposure_section(countries))

    routes = data.get("routeData")
    if routes:
        sections.append(_build_routes_section(routes))

    consumer = data.get("consumerImpact")
    if consumer:
        sections.append(_build_consumer_section(consumer))

    timeline = crisis.get("timeline")
    if timeline:
        sections.append(_build_timeline_section(timeline))

    return "\n<hr style='margin:2em 0;border:none;border-top:2px solid #e5e7eb'>\n".join(sections)


def _render_html(as_of, signal_rows, history_section, charts, tracker_data=None):
    charts_section = _build_charts_section(charts)
    tracker_sections = _build_tracker_sections(tracker_data)

    updated_note = ""
    if tracker_data and tracker_data.get("meta"):
        updated_note = f" | Data: {tracker_data['meta'].get('updated', '')[:10]}"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Hormuz Crisis Monitor</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 2em auto; padding: 0 1em; color: #1a1a1a; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: .3em; }}
  h2 {{ margin-top: 2em; color: #1e3a5f; border-bottom: 1px solid #e5e7eb; padding-bottom: .3em; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td, th {{ padding: 8px 10px; }}
  tbody tr {{ border-bottom: 1px solid #eee; }}
  tbody tr:hover {{ background: #f9f9f9; }}
  .footer {{ margin-top: 2em; font-size: .8em; color: #999; border-top: 1px solid #eee; padding-top: 1em; }}
</style></head><body>
<h1>Hormuz Crisis Monitor</h1>
<p style="color:#666">{as_of.strftime('%B %d, %Y')} -- India crude exposure dashboard{updated_note}</p>

<h2>Key Signals</h2>
<table>
  <thead>
    <tr style="border-bottom:2px solid #333">
      <th style="text-align:left">Signal</th>
      <th style="text-align:right">Value</th>
      <th>Status</th>
      <th style="text-align:left">Interpretation</th>
    </tr>
  </thead>
  <tbody>{signal_rows}</tbody>
</table>

{charts_section}

{history_section}

<hr style="margin:2em 0;border:none;border-top:2px solid #e5e7eb">

{tracker_sections}

<div class="footer">
  <p><strong>Sources:</strong> HormuzTracker (hormuztracker.com, CC BY 4.0) &bull;
  yfinance (Brent BZ=F, Dubai DCB=F) &bull;
  IMF PortWatch (AIS ship counts) &bull;
  S&P Global, UKMTO, Kpler, MarineTraffic, Clarksons Research</p>
  <p><strong>Signal thresholds:</strong>
  Insurance: GREEN &lt;1% | AMBER 1-2% | RED 2-5% | CRIT &gt;5% &bull;
  Ships: GREEN &gt;60 | AMBER 30-60 | RED 10-30 | CRIT &lt;10 &bull;
  Spread: GREEN &lt;$3 | AMBER $3-7 | RED $7-12 | CRIT &gt;$12 &bull;
  Cliff: GREEN &gt;30d | AMBER 14-30d | RED 7-14d | CRIT &lt;7d</p>
</div>
</body></html>"""
