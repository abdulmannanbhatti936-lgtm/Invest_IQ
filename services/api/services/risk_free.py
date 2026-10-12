"""
Risk-free rate for the backtest's Sharpe ratio (Phase 6): SBP's 3-month Market Treasury Bill
cut-off yield, from the versioned file written by integrations/sbp_tbills.py.

The rate for a day is the cut-off yield of the latest auction on or before it; an auction with
no yield (all bids rejected or none received) is skipped. MTB yields are simple per-annum
yields on a 365-day basis (checked on SBP's own prices; see the file's manifest), so the
risk-free return between two closes d calendar days apart is yield x d / 365.
"""

import bisect
import csv
import datetime
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from services.cost_engine import DATA_DIR

RISK_FREE_FILE = "sbp_mtb_3m_2026-09-30.csv"
DAYS_PER_YEAR = Decimal(365)


class RiskFreeUnavailable(Exception):
    """The file has no auction on or before a day the backtest needs."""


@dataclass(frozen=True)
class RiskFreeSeries:
    version: str
    source_url: str
    auction_dates: tuple[datetime.date, ...]
    yields: tuple[Decimal, ...]

    def yield_on(self, day: datetime.date) -> Decimal:
        position = bisect.bisect_right(self.auction_dates, day)
        if position == 0:
            raise RiskFreeUnavailable(f"No T-bill auction on or before {day}")
        return self.yields[position - 1]

    def interval_return(self, previous: datetime.date, current: datetime.date) -> Decimal:
        """Risk-free return from one close to the next, at the yield known at the first."""
        return self.yield_on(previous) * (current - previous).days / DAYS_PER_YEAR

    def summary(self, start: datetime.date, end: datetime.date) -> dict:
        used = [
            (d, y)
            for d, y in zip(self.auction_dates, self.yields, strict=True)
            if start <= d <= end
        ]
        return {
            "source": "SBP Market Treasury Bills, 3-month cut-off yield",
            "source_url": self.source_url,
            "version": self.version,
            "basis": "simple yield, 365-day year",
            "yield_at_start": str(self.yield_on(start)),
            "auctions_in_period": len(used),
            "lowest_yield": str(min(y for _, y in used)) if used else None,
            "highest_yield": str(max(y for _, y in used)) if used else None,
        }


def parse(path: Path) -> RiskFreeSeries:
    manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError(f"{path.name} does not match the SHA-256 in its manifest")
    dates, yields = [], []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["cutoff_yield"] in ("BR", "NBR"):
                continue
            dates.append(datetime.date.fromisoformat(row["auction_date"]))
            yields.append(Decimal(row["cutoff_yield"]))
    if dates != sorted(dates):
        raise ValueError(f"{path.name} is not in auction-date order")
    return RiskFreeSeries(manifest["version"], manifest["source_url"], tuple(dates), tuple(yields))


@lru_cache(maxsize=1)
def load() -> RiskFreeSeries:
    return parse(DATA_DIR / RISK_FREE_FILE)
