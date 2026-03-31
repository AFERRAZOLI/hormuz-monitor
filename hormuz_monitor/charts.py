"""
Generate base64-encoded PNG charts from historical signal data.

One chart per signal, plus a combined oil prices chart.
Threshold bands are shaded so you can see where you sit at a glance.
"""

import base64
import io
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

logger = logging.getLogger(__name__)

# Shared styling
BAND_ALPHA = 0.10
LINE_COLOR = "#1e3a5f"
MARKER_COLOR = "#ef4444"
GRID_ALPHA = 0.3


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _make_fig():
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.grid(True, alpha=GRID_ALPHA, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax


def chart_insurance(df: pd.DataFrame) -> str | None:
    """War-risk insurance premium over time with threshold bands."""
    col = "insurance_pct"
    subset = df.dropna(subset=[col])
    if len(subset) < 2:
        return None

    fig, ax = _make_fig()
    dates = pd.to_datetime(subset["date"])

    # Threshold bands
    ymax = max(subset[col].max() * 1.2, 6)
    ax.axhspan(0, 1, color="#22c55e", alpha=BAND_ALPHA, label="GREEN <1%")
    ax.axhspan(1, 2, color="#eab308", alpha=BAND_ALPHA, label="AMBER 1-2%")
    ax.axhspan(2, 5, color="#ef4444", alpha=BAND_ALPHA, label="RED 2-5%")
    ax.axhspan(5, ymax, color="#a855f7", alpha=BAND_ALPHA, label="CRIT >5%")

    # Pre-crisis reference
    ax.axhline(0.25, color="#22c55e", linewidth=1, linestyle=":", alpha=0.7)
    ax.text(dates.iloc[0], 0.35, "pre-crisis 0.25%", fontsize=7, color="#22c55e")

    ax.plot(dates, subset[col], color=LINE_COLOR, linewidth=2, marker="o",
            markersize=4, markerfacecolor=MARKER_COLOR, zorder=5)
    ax.set_ylabel("% of hull value")
    ax.set_title("War-Risk Insurance Premium", fontweight="bold", fontsize=11)
    ax.set_ylim(0, ymax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.legend(loc="upper right", fontsize=7, framealpha=0.8)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_base64(fig)


def chart_ships(df: pd.DataFrame) -> str | None:
    """Daily ship crossings through Hormuz."""
    col = "ship_count"
    subset = df.dropna(subset=[col])
    if len(subset) < 2:
        return None

    fig, ax = _make_fig()
    dates = pd.to_datetime(subset["date"])

    ymax = max(subset[col].max() * 1.3, 70)
    ax.axhspan(60, ymax, color="#22c55e", alpha=BAND_ALPHA, label="GREEN >60")
    ax.axhspan(30, 60, color="#eab308", alpha=BAND_ALPHA, label="AMBER 30-60")
    ax.axhspan(10, 30, color="#ef4444", alpha=BAND_ALPHA, label="RED 10-30")
    ax.axhspan(0, 10, color="#a855f7", alpha=BAND_ALPHA, label="CRIT <10")

    # Pre-crisis reference
    ax.axhline(100, color="#22c55e", linewidth=1, linestyle=":", alpha=0.7)
    ax.text(dates.iloc[0], 102, "pre-crisis 100+", fontsize=7, color="#22c55e")

    ax.bar(dates, subset[col], color=LINE_COLOR, width=0.7, zorder=5)
    ax.set_ylabel("ships / day")
    ax.set_title("Hormuz Ship Crossings (AIS)", fontweight="bold", fontsize=11)
    ax.set_ylim(0, ymax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.legend(loc="upper right", fontsize=7, framealpha=0.8)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_base64(fig)


def chart_oil_spread(df: pd.DataFrame) -> str | None:
    """Brent vs Dubai physical prices + spread."""
    has_brent = df["brent"].notna()
    has_dubai = df["dubai_physical"].notna()
    subset = df[has_brent & has_dubai]
    if len(subset) < 2:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                     gridspec_kw={"height_ratios": [2, 1]})
    for ax in (ax1, ax2):
        ax.grid(True, alpha=GRID_ALPHA, linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    dates = pd.to_datetime(subset["date"])

    # Top: price lines
    ax1.plot(dates, subset["brent"], color="#3b82f6", linewidth=2,
             marker="o", markersize=3, label="Brent (paper)")
    ax1.plot(dates, subset["dubai_physical"], color="#ef4444", linewidth=2,
             marker="s", markersize=3, label="Dubai Physical")
    ax1.set_ylabel("$/bbl")
    ax1.set_title("Paper vs Physical Crude", fontweight="bold", fontsize=11)
    ax1.legend(loc="upper left", fontsize=8)

    # Bottom: spread bars
    spread = subset["dubai_physical"].values - subset["brent"].values
    colors = ["#ef4444" if s > 3 else "#22c55e" for s in spread]
    ax2.bar(dates, spread, color=colors, width=0.7)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.axhline(3, color="#eab308", linewidth=1, linestyle="--", alpha=0.5)
    ax2.axhline(7, color="#ef4444", linewidth=1, linestyle="--", alpha=0.5)
    ax2.axhline(12, color="#a855f7", linewidth=1, linestyle="--", alpha=0.5)
    ax2.set_ylabel("Spread $/bbl")
    ax2.set_xlabel("")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return _fig_to_base64(fig)


def chart_cliff(df: pd.DataFrame) -> str | None:
    """Countdown to April cliff."""
    col = "cliff_days"
    subset = df.dropna(subset=[col])
    if len(subset) < 2:
        return None

    fig, ax = _make_fig()
    dates = pd.to_datetime(subset["date"])

    ymax = max(subset[col].max() * 1.2, 35)
    ax.axhspan(30, ymax, color="#22c55e", alpha=BAND_ALPHA, label="GREEN >30d")
    ax.axhspan(14, 30, color="#eab308", alpha=BAND_ALPHA, label="AMBER 14-30d")
    ax.axhspan(7, 14, color="#ef4444", alpha=BAND_ALPHA, label="RED 7-14d")
    ax.axhspan(0, 7, color="#a855f7", alpha=BAND_ALPHA, label="CRIT <7d")

    ax.plot(dates, subset[col], color=LINE_COLOR, linewidth=2, marker="o",
            markersize=4, markerfacecolor=MARKER_COLOR, zorder=5)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylabel("days remaining")
    ax.set_title("April Cliff Countdown", fontweight="bold", fontsize=11)
    ax.set_ylim(-1, ymax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.legend(loc="upper right", fontsize=7, framealpha=0.8)
    fig.autofmt_xdate(rotation=30)
    return _fig_to_base64(fig)


def generate_all_charts(history: pd.DataFrame) -> dict[str, str]:
    """Generate all charts, returning {name: base64_png}. Skips if <2 points."""
    charts = {}
    for name, fn in [
        ("insurance", chart_insurance),
        ("ships", chart_ships),
        ("oil_spread", chart_oil_spread),
        ("cliff", chart_cliff),
    ]:
        try:
            b64 = fn(history)
            if b64:
                charts[name] = b64
        except Exception as e:
            logger.warning(f"Chart '{name}' failed: {e}")
    return charts
