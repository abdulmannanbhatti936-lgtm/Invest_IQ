"""
SBP Market Treasury Bill auction history (the backtest's risk-free rate, Phase 6).

SBP publishes every MTB auction in https://www.sbp.org.pk/assets/document/tb.xlsx (sheet
"New Detailed Format"). This module reads that workbook with the standard library (an .xlsx
file is a zip of XML) and writes the 3-month cut-off yields to a versioned CSV in
integrations/data, with a manifest recording the source file's SHA-256.

SBP's investor guide does not state the yield's day-count basis, so `basis_check` tests it on
SBP's own figures: yield = (100 / cut-off price - 1) x 365 / days to maturity.

    python -m integrations.sbp_tbills path/to/tb.xlsx
"""

import csv
import datetime
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

DATA_DIR = Path(__file__).parent / "data"
SOURCE_URL = "https://www.sbp.org.pk/assets/document/tb.xlsx"
SHEET_NAME = "New Detailed Format"
TENOR = "3-Month"
# No cut-off yield: "BR" = SBP rejected all bids, "NBR" = no bids received
NO_YIELD_CODES = ("BR", "NBR")

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_EXCEL_EPOCH = datetime.date(1899, 12, 30)


@dataclass(frozen=True)
class Auction:
    auction_date: datetime.date
    issue_date: datetime.date
    maturity_date: datetime.date
    tenor: str
    cutoff_price: Decimal | None
    cutoff_yield: Decimal | None
    no_yield_code: str | None  # 'BR' / 'NBR' when there is no cut-off yield


def _column(ref: str) -> int:
    number = 0
    for letter in re.match(r"[A-Z]+", ref).group():
        number = number * 26 + ord(letter) - 64
    return number - 1


def _sheet_rows(workbook: zipfile.ZipFile, name: str) -> list[list[str | None]]:
    shared = []
    if "xl/sharedStrings.xml" in workbook.namelist():
        root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
        shared = [
            "".join(t.text or "" for t in item.iter(_NS + "t")) for item in root.iter(_NS + "si")
        ]

    book = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    sheet = next((s for s in book.iter(_NS + "sheet") if s.get("name") == name), None)
    if sheet is None:
        raise ValueError(f"Sheet '{name}' not found")
    path = "xl/" + targets[sheet.get(_REL_NS + "id")].lstrip("/").removeprefix("xl/")

    rows = []
    for row in ElementTree.fromstring(workbook.read(path)).iter(_NS + "row"):
        # Empty cells are omitted from the XML, so each value is placed by its reference
        cells = {}
        for cell in row.iter(_NS + "c"):
            value = cell.find(_NS + "v")
            if value is None:
                continue
            text = shared[int(value.text)] if cell.get("t") == "s" else value.text
            cells[_column(cell.get("r"))] = text
        rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
    return rows


def _date(serial: str) -> datetime.date:
    return _EXCEL_EPOCH + datetime.timedelta(days=int(float(serial)))


def _number(text: str | None) -> Decimal | None:
    if text is None or text.strip() in NO_YIELD_CODES:
        return None
    return Decimal(text.strip())


def _code(text: str | None) -> str | None:
    return text.strip() if text and text.strip() in NO_YIELD_CODES else None


def read_auctions(path: Path) -> list[Auction]:
    """Every auction row of the detailed sheet, in file order."""
    with zipfile.ZipFile(path) as workbook:
        rows = _sheet_rows(workbook, SHEET_NAME)

    header_at = next(i for i, row in enumerate(rows) if "Auction Date" in row)
    columns = {name: i for i, name in enumerate(rows[header_at]) if name}
    # The yield and price headings sit on the second header row
    columns.update({name.strip(): i for i, name in enumerate(rows[header_at + 1]) if name})
    needed = ["Tenure", "Auction Date", "Issue Date", "Maturity Date", "Cut-off Price"]
    needed.append("Cut-off Yield")

    auctions = []
    for row in rows[header_at + 2 :]:
        cells = {name: row[i] if i < len(row) else None for name, i in columns.items()}
        if not cells.get("Tenure") or not re.fullmatch(r"[\d.]+", cells.get("Auction Date") or ""):
            continue
        missing = [n for n in needed if n not in cells]
        if missing:
            raise ValueError(f"Columns not found: {missing}")
        auctions.append(
            Auction(
                auction_date=_date(cells["Auction Date"]),
                issue_date=_date(cells["Issue Date"]),
                maturity_date=_date(cells["Maturity Date"]),
                tenor=cells["Tenure"].strip(),
                cutoff_price=_number(cells["Cut-off Price"]),
                cutoff_yield=_number(cells["Cut-off Yield"]),
                no_yield_code=_code(cells["Cut-off Yield"]),
            )
        )
    return auctions


def basis_check(auctions: list[Auction], tolerance: Decimal = Decimal("0.000001")) -> dict:
    """How many auctions SBP's own price reproduces on a 365-day and on a 360-day basis."""
    priced = [a for a in auctions if a.cutoff_price and a.cutoff_yield is not None]
    matches = {}
    for basis in (365, 360):
        matches[basis] = sum(
            1
            for a in priced
            if abs(
                (Decimal(100) / a.cutoff_price - 1) * basis / (a.maturity_date - a.issue_date).days
                - a.cutoff_yield
            )
            < tolerance
        )
    return {"auctions": len(priced), "match_365": matches[365], "match_360": matches[360]}


def write_dataset(xlsx: Path, out_dir: Path = DATA_DIR) -> Path:
    auctions = read_auctions(xlsx)
    three_month = sorted((a for a in auctions if a.tenor == TENOR), key=lambda a: a.auction_date)
    last = three_month[-1].auction_date
    version = f"sbp-mtb-3m-{last.isoformat()}"
    csv_path = out_dir / f"sbp_mtb_3m_{last.isoformat()}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["auction_date", "cutoff_yield"])
        for auction in three_month:
            writer.writerow(
                [
                    auction.auction_date.isoformat(),
                    auction.no_yield_code or str(auction.cutoff_yield),
                ]
            )
    manifest = {
        "version": version,
        "file": csv_path.name,
        "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "source_url": SOURCE_URL,
        "source_sheet": SHEET_NAME,
        "source_sha256": hashlib.sha256(xlsx.read_bytes()).hexdigest(),
        "tenor": TENOR,
        "column": "Cut-off Yield (fraction per annum; 'BR' = all bids rejected, 'NBR' = no bids)",
        "auctions": len(three_month),
        "first_auction": three_month[0].auction_date.isoformat(),
        "last_auction": last.isoformat(),
        "basis_check": basis_check(auctions),
    }
    manifest_path = csv_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return csv_path


if __name__ == "__main__":
    written = write_dataset(Path(sys.argv[1]))
    print(written.with_suffix(".json").read_text(encoding="utf-8"))
