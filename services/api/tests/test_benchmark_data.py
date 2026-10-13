"""
Step 6.2: the data behind the benchmark and the Sharpe ratio. The SBP T-bill extractor runs on
a small workbook built here in SBP's layout; the KSE-100 loader runs on a MOCK file (no
licensed KSE-100 data exists yet, Memory.md §4).
"""

import datetime
import hashlib
import json
import shutil
import zipfile
from decimal import Decimal as D
from pathlib import Path

import pytest

from integrations import sbp_tbills
from models.backtest import IndexPoint
from services import index_data, risk_free
from services.index_data import IndexFile, IndexFileError, SpotCheck, validate

FIXTURES = Path(__file__).parent / "fixtures"
day = datetime.date.fromisoformat


def _excel_serial(value: str) -> str:
    return str((day(value) - datetime.date(1899, 12, 30)).days)


def _workbook(path: Path, rows: list[list[str | None]]) -> Path:
    """A minimal .xlsx with SBP's sheet name and inline numbers / shared strings."""
    strings: list[str] = []

    def cell(ref: str, value: str | None) -> str:
        if value is None:
            return ""
        try:
            float(value)
            return f'<c r="{ref}"><v>{value}</v></c>'
        except ValueError:
            strings.append(value)
            return f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>'

    body = "".join(
        f'<row r="{r + 1}">'
        + "".join(cell(f"{chr(65 + c)}{r + 1}", v) for c, v in enumerate(row))
        + "</row>"
        for r, row in enumerate(rows)
    )
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f'<workbook {ns} {rel}><sheets><sheet name="Old Format" sheetId="1" r:id="rId1"/>'
            f'<sheet name="New Detailed Format" sheetId="2" r:id="rId2"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData/></worksheet>")
        z.writestr(
            "xl/worksheets/sheet2.xml", f"<worksheet {ns}><sheetData>{body}</sheetData></worksheet>"
        )
        z.writestr(
            "xl/sharedStrings.xml",
            f"<sst {ns}>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>",
        )
    return path


def _auction(no, tenor, auction, issue, maturity, price, yld):
    row = [no, tenor, "ISIN", _excel_serial(auction), _excel_serial(issue), _excel_serial(maturity)]
    return row + [None] * 8 + [price, yld, None]


SBP_ROWS = [
    ["HISTORICAL DATA OF MARKET TREASURY BILLS"],
    ["Auction Number", "Tenure", "ISIN", "Auction Date", "Issue Date", "Maturity Date"],
    [None] * 14 + ["Cut-off Price", "Cut-off Yield", "Weighted Average YIeld"],
    # SBP's real 30 Sep 2026 3-month auction: 97.3138 for 84 days = 11.99437...% on 365 days
    _auction("1", "3-Month", "2026-09-30", "2026-10-01", "2026-12-24", "97.3138",
             "0.11994371375312204"),
    _auction("1", "6-Month", "2026-09-30", "2026-10-01", "2027-03-25", "94.3019", "0.124500"),
    _auction("2", "3-Month", "2024-10-02", "2024-10-03", "2024-12-26", "BR", "BR"),
    _auction("3", "3-Month", "2023-10-04", "2023-10-05", "2023-12-28", "NBR", "NBR"),
]  # fmt: skip


def test_sbp_extractor_writes_three_month_yields_with_codes_and_manifest(tmp_path):
    xlsx = _workbook(tmp_path / "tb.xlsx", SBP_ROWS)
    csv_path = sbp_tbills.write_dataset(xlsx, tmp_path)

    assert csv_path.name == "sbp_mtb_3m_2026-09-30.csv"
    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "auction_date,cutoff_yield",
        "2023-10-04,NBR",
        "2024-10-02,BR",
        "2026-09-30,0.11994371375312204",
    ]
    manifest = json.loads(csv_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["version"] == "sbp-mtb-3m-2026-09-30"
    assert manifest["auctions"] == 3
    assert manifest["sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert manifest["source_sha256"] == hashlib.sha256(xlsx.read_bytes()).hexdigest()


def test_basis_check_finds_sbp_yields_are_simple_365_day_yields(tmp_path):
    auctions = sbp_tbills.read_auctions(_workbook(tmp_path / "tb.xlsx", SBP_ROWS))
    # Only the 3-month row carries SBP's exact price and yield
    check = sbp_tbills.basis_check(auctions[:1])
    assert check == {"auctions": 1, "match_365": 1, "match_360": 0}


def test_committed_risk_free_file_matches_its_manifest_and_sbp_figures():
    series = risk_free.load()
    assert series.version == "sbp-mtb-3m-2026-09-30"
    # Cross-checked against SBP's auction result PDF for 30 Sep 2026: 11.9944%
    assert series.yield_on(day("2026-09-30")).quantize(D("0.000001")) == D("0.119944")
    assert series.yield_on(day("2023-10-04")).quantize(D("0.0001")) == D("0.2250")
    # 2 Oct 2024: all bids rejected, so the 18 Sep 2024 auction still applies
    assert series.yield_on(day("2024-10-02")) == series.yield_on(day("2024-10-01"))


def test_rate_is_the_latest_auction_on_or_before_and_accrues_simply_over_calendar_days():
    series = risk_free.RiskFreeSeries(
        "MOCK", "", (day("2025-01-01"), day("2025-01-15")), (D("0.12"), D("0.10"))
    )
    assert series.yield_on(day("2025-01-14")) == D("0.12")
    assert series.yield_on(day("2025-01-15")) == D("0.10")
    # Friday to Monday is 3 calendar days at the rate known on Friday
    assert series.interval_return(day("2025-01-10"), day("2025-01-13")) == D("0.12") * 3 / 365
    with pytest.raises(risk_free.RiskFreeUnavailable):
        series.yield_on(day("2024-12-31"))


def test_risk_free_file_with_a_changed_byte_is_refused(tmp_path):
    for suffix in (".csv", ".json"):
        shutil.copy(
            risk_free.DATA_DIR / risk_free.RISK_FREE_FILE.replace(".csv", suffix),
            tmp_path / ("rf" + suffix),
        )
    path = tmp_path / "rf.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("0.2250", "0.2251"), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        risk_free.parse(path)


TRADING_DAYS = {day(d) for d in ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06",
                                 "2025-01-07", "2025-01-08", "2025-01-09"]}  # fmt: skip


def _mock() -> IndexFile:
    return index_data.read_file(FIXTURES / "MOCK_kse100.csv")


def test_validation_flags_gaps_stale_closes_and_large_moves():
    report = validate(_mock(), TRADING_DAYS | {day("2024-12-31")})
    assert report.errors == []
    assert (report.first_date, report.last_date, report.points) == ("2025-01-01", "2025-01-09", 6)
    # 8 Jan traded but has no close; 31 Dec is before the file starts, so it is not missing
    assert report.missing_days == ["2025-01-08"]
    assert report.extra_days == []
    assert report.stale_runs == [{"from": "2025-01-02", "to": "2025-01-03", "close": "1010.00"}]
    # 1010.00 -> 1061.00 is +5.05%: just over the 5% line
    assert report.large_moves == [{"date": "2025-01-06", "change": "0.050495"}]
    assert report.flagged


def test_validation_refuses_repeated_dates_bad_closes_and_failed_spot_checks():
    index = IndexFile("KSE100", "MOCK", "MOCK", [(day("2025-01-01"), D("1000")),
                      (day("2025-01-01"), D("1001")), (day("2025-01-02"), D("0"))])  # fmt: skip
    report = validate(index, TRADING_DAYS)
    assert report.errors == [
        "2025-01-01 appears more than once",
        "2025-01-02: close 0 is not positive",
    ]

    checks = [SpotCheck(day("2025-01-06"), D("1061.00"), "MOCK report A"),
              SpotCheck(day("2025-01-07"), D("1050.02"), "MOCK report B")]  # fmt: skip
    report = validate(_mock(), TRADING_DAYS, checks)
    assert [c["ok"] for c in report.spot_checks] == [True, False]
    assert report.errors == ["2025-01-07: file has 1050.00, MOCK report B published 1050.02"]


def test_total_return_index_must_grow_at_least_as_much_as_its_price_version():
    price_only = [(day("2025-01-01"), D("500")), (day("2025-01-09"), D("530"))]  # +6.0%
    report = validate(_mock(), TRADING_DAYS, other_version=price_only)  # KSE100 +4.0%
    assert report.total_return_check["ok"] is False
    assert report.flagged


def test_manifest_mismatch_is_refused(tmp_path):
    for name in ("MOCK_kse100.csv", "MOCK_kse100.json"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    (tmp_path / "MOCK_kse100.csv").write_text("date,close\n2025-01-01,999\n", encoding="utf-8")
    with pytest.raises(IndexFileError, match="SHA-256"):
        index_data.read_file(tmp_path / "MOCK_kse100.csv")


def _copy_fixture(tmp_path) -> Path:
    for name in ("MOCK_kse100.csv", "MOCK_kse100.json"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    return tmp_path / "MOCK_kse100.csv"


def test_mock_files_never_load_outside_tests(db, tmp_path):
    with pytest.raises(IndexFileError, match="MOCK"):
        index_data.load(db, _copy_fixture(tmp_path))
    assert db.query(IndexPoint).count() == 0


def test_load_stores_the_version_writes_its_report_and_refuses_a_second_load(db, tmp_path):
    path = _copy_fixture(tmp_path)
    report = index_data.load(db, path, allow_mock=True)

    assert report.errors == []
    version, closes = index_data.latest_series(db, "KSE100")
    assert version == "MOCK-kse100-test"
    assert closes[day("2025-01-06")] == D("1061.0000")
    saved = json.loads((tmp_path / "MOCK_kse100.validation.json").read_text(encoding="utf-8"))
    assert saved["large_moves"] == [{"date": "2025-01-06", "change": "0.050495"}]
    with pytest.raises(IndexFileError, match="already loaded"):
        index_data.load(db, path, allow_mock=True)


def test_failed_spot_check_stores_nothing(db, tmp_path):
    path = _copy_fixture(tmp_path)
    checks = tmp_path / "published.csv"
    checks.write_text("date,close,source\n2025-01-07,1049.00,MOCK report\n", encoding="utf-8")
    with pytest.raises(IndexFileError, match="MOCK report published 1049.00"):
        index_data.load(db, path, checks, allow_mock=True)
    assert index_data.latest_series(db, "KSE100") is None
