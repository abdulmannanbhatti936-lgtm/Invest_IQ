"""
Daily index closes for the backtest benchmark (PRD.md FR32, Phase 6).

No source may be scraped for the KSE-100 (Memory.md §4: PSX's terms forbid systematic
retrieval and storage without written permission), so a licensed file is loaded by hand:

    python -m services.index_data load path/to/kse100.csv [--spot-checks published.csv]

The CSV has `date,close`; beside it a manifest `<same name>.json` gives index_code
('KSE100' or 'KSE100PR'), dataset_version, source and the CSV's SHA-256. Spot checks are
`date,close,source` rows of figures published elsewhere (e.g. PSX market reports).

Hard errors refuse the load: a bad row, a non-positive close, a repeated date, a manifest
mismatch or a spot check off by more than 0.01 points. Soft flags are reported for a person
to review: days the market traded with no index close (and the reverse), the same close on
consecutive days, daily moves over 5%, and a total-return index growing less than its price
version. Every load writes its report to `<same name>.validation.json`.
"""

import argparse
import csv
import datetime
import hashlib
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.backtest import IndexPoint
from models.stock import PricePoint
from services.stock_service import PSX_TRADING_DATE, SERVED

INDEX_CODES = ("KSE100", "KSE100PR")
TOTAL_RETURN_PAIR = ("KSE100", "KSE100PR")  # KSE100 reinvests cash dividends; KSE100PR does not
LARGE_MOVE = Decimal("0.05")
SPOT_CHECK_TOLERANCE = Decimal("0.01")
# A day is a trading day when at least half the stocks with history by then have a served bar
TRADING_DAY_SHARE = Decimal("0.5")
MOCK_PREFIX = "MOCK"


class IndexFileError(ValueError):
    """The file cannot be loaded; the message lists every problem found."""


@dataclass(frozen=True)
class IndexFile:
    index_code: str
    dataset_version: str
    source: str
    points: list[tuple[datetime.date, Decimal]]


@dataclass(frozen=True)
class SpotCheck:
    day: datetime.date
    close: Decimal
    source: str


@dataclass
class ValidationReport:
    index_code: str
    dataset_version: str
    first_date: str | None = None
    last_date: str | None = None
    points: int = 0
    errors: list[str] = field(default_factory=list)
    missing_days: list[str] = field(default_factory=list)
    extra_days: list[str] = field(default_factory=list)
    stale_runs: list[dict] = field(default_factory=list)
    large_moves: list[dict] = field(default_factory=list)
    spot_checks: list[dict] = field(default_factory=list)
    total_return_check: dict | None = None

    @property
    def flagged(self) -> bool:
        return bool(
            self.missing_days
            or self.extra_days
            or self.stale_runs
            or self.large_moves
            or (self.total_return_check and not self.total_return_check["ok"])
        )


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text.strip().replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"not a number: {text!r}") from exc


def read_file(path: Path) -> IndexFile:
    manifest_path = path.with_suffix(".json")
    if not manifest_path.exists():
        raise IndexFileError(f"Manifest {manifest_path.name} is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = [
        f"manifest has no '{k}'"
        for k in ("index_code", "dataset_version", "source", "sha256")
        if not manifest.get(k)
    ]
    if manifest.get("index_code") and manifest["index_code"] not in INDEX_CODES:
        problems.append(f"index_code must be one of {INDEX_CODES}")
    if (
        manifest.get("sha256")
        and hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]
    ):
        problems.append("the CSV does not match the SHA-256 in its manifest")
    if problems:
        raise IndexFileError("; ".join(problems))

    points = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            try:
                points.append(
                    (datetime.date.fromisoformat(row["date"].strip()), _decimal(row["close"]))
                )
            except (KeyError, ValueError, AttributeError) as exc:
                problems.append(f"line {line}: {exc}")
    if problems:
        raise IndexFileError("; ".join(problems))
    return IndexFile(
        manifest["index_code"], manifest["dataset_version"], manifest["source"], points
    )


def read_spot_checks(path: Path) -> list[SpotCheck]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            SpotCheck(
                datetime.date.fromisoformat(r["date"].strip()),
                _decimal(r["close"]),
                r["source"].strip(),
            )
            for r in csv.DictReader(handle)
        ]


def validate(
    index: IndexFile,
    trading_days: set[datetime.date],
    spot_checks: list[SpotCheck] = (),
    other_version: list[tuple[datetime.date, Decimal]] | None = None,
) -> ValidationReport:
    """
    Checks a file against the market's trading days and published figures. `other_version`
    is the loaded series of the index's pair (KSE100 vs KSE100PR) for the total-return check.
    """
    report = ValidationReport(index.index_code, index.dataset_version, points=len(index.points))
    seen: dict[datetime.date, Decimal] = {}
    for day, close in index.points:
        if day in seen:
            report.errors.append(f"{day} appears more than once")
        if close <= 0:
            report.errors.append(f"{day}: close {close} is not positive")
        seen[day] = close
    if not seen:
        report.errors.append("the file has no rows")
        return report

    days = sorted(seen)
    report.first_date, report.last_date = days[0].isoformat(), days[-1].isoformat()
    in_range = {d for d in trading_days if days[0] <= d <= days[-1]}
    report.missing_days = [d.isoformat() for d in sorted(in_range - seen.keys())]
    report.extra_days = [d.isoformat() for d in sorted(seen.keys() - trading_days)]

    run_start = None
    for previous, current in zip(days, days[1:], strict=False):
        if seen[current] == seen[previous]:
            run_start = run_start or previous
            continue
        if run_start:
            report.stale_runs.append(
                {
                    "from": run_start.isoformat(),
                    "to": previous.isoformat(),
                    "close": str(seen[previous]),
                }
            )
            run_start = None
        if seen[previous] > 0:
            move = seen[current] / seen[previous] - 1
            if abs(move) > LARGE_MOVE:
                report.large_moves.append(
                    {"date": current.isoformat(), "change": str(round(move, 6))}
                )
    if run_start:
        report.stale_runs.append(
            {
                "from": run_start.isoformat(),
                "to": days[-1].isoformat(),
                "close": str(seen[days[-1]]),
            }
        )

    for check in spot_checks:
        ours = seen.get(check.day)
        ok = ours is not None and abs(ours - check.close) <= SPOT_CHECK_TOLERANCE
        report.spot_checks.append(
            {
                "date": check.day.isoformat(),
                "published": str(check.close),
                "file": None if ours is None else str(ours),
                "source": check.source,
                "ok": ok,
            }
        )
        if not ok:
            report.errors.append(
                f"{check.day}: file has {ours}, {check.source} published {check.close}"
            )

    if other_version:
        report.total_return_check = _total_return_check(index.index_code, seen, dict(other_version))
    return report


def _total_return_check(code: str, ours: dict, other: dict) -> dict | None:
    common = sorted(ours.keys() & other.keys())
    if len(common) < 2:
        return None
    first, last = common[0], common[-1]
    growth = {
        code: ours[last] / ours[first],
        ("KSE100PR" if code == "KSE100" else "KSE100"): other[last] / other[first],
    }
    total, price = growth[TOTAL_RETURN_PAIR[0]], growth[TOTAL_RETURN_PAIR[1]]
    return {
        "from": first.isoformat(),
        "to": last.isoformat(),
        "kse100_growth": str(round(total, 6)),
        "kse100pr_growth": str(round(price, 6)),
        "ok": total >= price,
    }


def expected_trading_days(db: Session) -> set[datetime.date]:
    counts = dict(
        db.query(PSX_TRADING_DATE, func.count(func.distinct(PricePoint.stock_id)))
        .filter(SERVED)
        .group_by(PSX_TRADING_DATE)
        .all()
    )
    firsts = sorted(
        first
        for (first,) in db.query(func.min(PSX_TRADING_DATE))
        .filter(SERVED)
        .group_by(PricePoint.stock_id)
    )
    days = set()
    for day, count in counts.items():
        listed = sum(1 for first in firsts if first <= day)
        if listed and Decimal(count) / listed >= TRADING_DAY_SHARE:
            days.add(day)
    return days


def latest_series(db: Session, index_code: str) -> tuple[str, dict[datetime.date, Decimal]] | None:
    """The newest loaded version of an index, or None when none has been loaded."""
    newest = (
        db.query(IndexPoint.dataset_version)
        .filter(IndexPoint.index_code == index_code)
        .order_by(IndexPoint.loaded_at.desc(), IndexPoint.id.desc())
        .first()
    )
    if newest is None:
        return None
    rows = db.query(IndexPoint.trade_date, IndexPoint.close).filter(
        IndexPoint.index_code == index_code, IndexPoint.dataset_version == newest[0]
    )
    return newest[0], {day: Decimal(close) for day, close in rows}


def load(
    db: Session, path: Path, spot_checks_path: Path | None = None, allow_mock: bool = False
) -> ValidationReport:
    index = read_file(path)
    if index.dataset_version.upper().startswith(MOCK_PREFIX) and not allow_mock:
        raise IndexFileError(
            "MOCK datasets are for tests only and are never loaded into this database"
        )
    if (
        db.query(IndexPoint.id)
        .filter(
            IndexPoint.index_code == index.index_code,
            IndexPoint.dataset_version == index.dataset_version,
        )
        .first()
    ):
        raise IndexFileError(f"{index.index_code} {index.dataset_version} is already loaded")

    pair = (
        TOTAL_RETURN_PAIR[1] if index.index_code == TOTAL_RETURN_PAIR[0] else TOTAL_RETURN_PAIR[0]
    )
    other = latest_series(db, pair)
    spot_checks = read_spot_checks(spot_checks_path) if spot_checks_path else []
    report = validate(
        index, expected_trading_days(db), spot_checks, sorted(other[1].items()) if other else None
    )
    path.with_name(path.stem + ".validation.json").write_text(
        json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if report.errors:
        raise IndexFileError("; ".join(report.errors))

    db.add_all(
        IndexPoint(
            index_code=index.index_code,
            dataset_version=index.dataset_version,
            trade_date=day,
            close=close,
            source=index.source,
        )
        for day, close in index.points
    )
    db.commit()
    return report


def main() -> None:
    from core.database import SessionLocal

    parser = argparse.ArgumentParser(description="Load a licensed daily index file")
    parser.add_argument("command", choices=["load"])
    parser.add_argument("csv", type=Path)
    parser.add_argument("--spot-checks", type=Path)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        report = load(db, args.csv, args.spot_checks)
    finally:
        db.close()
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
