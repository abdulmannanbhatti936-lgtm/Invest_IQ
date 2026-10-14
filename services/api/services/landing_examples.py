"""
The landing page's risk demo (UI round, 2026-10-15): the engine's real allocation of
Rs 100,000 for a filer under each risk profile, computed from the stored prices and forecasts
and written once as a dated JSON file. Nothing is stored in the database. Run from
services/api:

    python -m services.landing_examples ../../apps/web/src/features/landing/data

It writes risk-examples.json (tickers) and risk-examples-sectors.json (sector names only, for
a public deployment before PSX answers; Memory.md §4). The page labels both "Example, prices as
of <date>, not advice". It also writes the hero bloom's companies from the dated KSE-100
snapshot: bloom-companies.json (ticker and sector) and bloom-sectors.json (sector only).
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import SessionLocal
from integrations.psx_catalog import SNAPSHOT_FILE, load_snapshot
from models.risk_profile import RiskCategory
from services import portfolio_service
from services.cost_engine import FilerStatus
from services.portfolio_service import PortfolioInputs, plan_allocation
from services.prediction_service import covered_tickers
from services.stock_service import PSX_TRADING_DATE, SERVED

CAPITAL = Decimal("100000")


def _pct(part: Decimal) -> str:
    # The same rounding as a stored holding's allocation_pct (portfolio_service)
    return str(portfolio_service._pct(part / CAPITAL, "0.0001"))


def _history_start(db: Session):
    """The first PSX trading date of any served price we store (None when there are none)."""
    first = db.query(func.min(PSX_TRADING_DATE)).filter(SERVED).scalar()
    return first.isoformat() if first else None


def build(db: Session) -> dict:
    inputs = PortfolioInputs(
        capital=CAPITAL,
        filer_status=FilerStatus.filer,
        shariah_only=False,
        excluded_tickers=[],
        commission_rate=None,
    )
    profiles, meta = {}, {}
    for category in RiskCategory:
        plan = plan_allocation(db, category.value, inputs)
        meta = {
            # Facts the landing page quotes, each from our own data
            "forecast_companies": len(covered_tickers()),
            "history_start": _history_start(db),
            "capital": str(CAPITAL),
            "filer_status": "filer",
            "prices_as_of": plan.universe.prices_as_of.isoformat(),
            "model_version": plan.universe.model_version,
            "rates_version": plan.rates.version,
        }
        profiles[category.value] = {
            "holdings": [
                {
                    "ticker": h.scored.ticker,
                    "sector": plan.universe.eligible[h.scored.ticker].stock.sector,
                    "allocation_pct": _pct(h.purchase.total_cost),
                }
                for h in plan.allocation.holdings
            ],
            "cash_pct": _pct(plan.allocation.idle.amount),
        }
    return {**meta, "profiles": profiles}


def sectors_only(example: dict) -> dict:
    """The same example with every ticker removed (sector names only)."""
    return {
        **example,
        "profiles": {
            name: {
                **profile,
                "holdings": [
                    {k: v for k, v in h.items() if k != "ticker"} for h in profile["holdings"]
                ],
            }
            for name, profile in example["profiles"].items()
        },
    }


def bloom(with_tickers: bool) -> dict:
    """One ray per included snapshot company; the snapshot date is in the file name."""
    companies = load_snapshot()
    return {
        "snapshot": SNAPSHOT_FILE.stem.removeprefix("kse100_snapshot_"),
        "companies": [
            {"ticker": c.ticker, "sector": c.sector} if with_tickers else {"sector": c.sector}
            for c in companies
        ],
    }


def main(out_dir: str) -> None:
    with SessionLocal() as db:
        example = build(db)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("risk-examples.json", example),
        ("risk-examples-sectors.json", sectors_only(example)),
        ("bloom-companies.json", bloom(with_tickers=True)),
        ("bloom-sectors.json", bloom(with_tickers=False)),
    ):
        (out / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"prices as of {example['prices_as_of']}, model {example['model_version']}")


if __name__ == "__main__":
    main(sys.argv[1])
