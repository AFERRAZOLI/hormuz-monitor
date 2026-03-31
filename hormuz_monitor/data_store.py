"""
Local CSV-based storage for historical signal readings.

Stores daily snapshots so you can track trend direction.
File: <output_dir>/hormuz_history.csv
"""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

COLUMNS = [
    "date",
    "insurance_pct",
    "ship_count",
    "brent",
    "dubai_physical",
    "spread",
    "cliff_days",
    "notes",
]

DEFAULT_PATH = Path("output/hormuz_history.csv")


def _ensure_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(COLUMNS)
    return path


def append_reading(
    path: Path = DEFAULT_PATH,
    *,
    as_of: date | None = None,
    insurance_pct: float | None = None,
    ship_count: float | None = None,
    brent: float | None = None,
    dubai_physical: float | None = None,
    spread: float | None = None,
    cliff_days: int | None = None,
    notes: str = "",
) -> None:
    """Append a single row to the history CSV."""
    path = _ensure_file(path)
    as_of = as_of or date.today()

    row = [
        as_of.isoformat(),
        insurance_pct,
        ship_count,
        brent,
        dubai_physical,
        spread,
        cliff_days,
        notes,
    ]
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow(row)


def load_history(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    """Load the full history as a DataFrame."""
    path = _ensure_file(path)
    df = pd.read_csv(path, parse_dates=["date"])
    for col in ["insurance_pct", "ship_count", "brent", "dubai_physical", "spread", "cliff_days"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_latest(path: Path = DEFAULT_PATH) -> dict | None:
    """Return the most recent reading as a dict, or None."""
    df = load_history(path)
    if df.empty:
        return None
    return df.iloc[-1].to_dict()
