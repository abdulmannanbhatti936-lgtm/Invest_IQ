"""
The stock universe: a fixed, versioned snapshot of the KSE-100 index (PRD.md FR9).

The constituents change twice a year, so the app never reads a live list. A new snapshot is a
new file plus a migration that seeds it; earlier snapshots stay in the repo for traceability.
Only constituents with at least 3 years of Yahoo Finance history are included; the file
records why each excluded ticker was left out.
"""

import csv
from pathlib import Path
from typing import NamedTuple

SNAPSHOT_FILE = Path(__file__).parent / "data" / "kse100_snapshot_2026-10-10.csv"


class Company(NamedTuple):
    ticker: str
    name: str
    sector: str


def load_snapshot(path: Path = SNAPSHOT_FILE) -> list[Company]:
    """Included companies from a snapshot file, ordered by ticker."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["included"] == "true"]
    return sorted(
        (Company(r["ticker"], r["name"], r["sector"]) for r in rows), key=lambda c: c.ticker
    )


PSX_COMPANIES = load_snapshot()
CATALOG_BY_TICKER = {c.ticker: (c.name, c.sector) for c in PSX_COMPANIES}
