# -*- coding: utf-8 -*-
"""Generate demo fixture files under poc/fixtures/ for Excel guard POC."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

FIXTURES_DIR = Path(__file__).resolve().parent


def write_corrupt_xlsx(path: Path) -> None:
    path.write_bytes(b"NOT_A_VALID_XLSX_OR_ZIP_PACKAGE_FOR_POC_DEMO")


def write_encoding_latin1_csv(path: Path) -> None:
    # Latin-1 content with non-UTF-8 bytes (é, ü)
    text = "id,name,city\n1,Jos\xe9,M\xfcnchen\n2,Fran\xe7ois,Caf\xe9\n"
    path.write_bytes(text.encode("latin-1"))


def write_large_chunk_demo_xlsx(path: Path, rows: int = 6000) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "DemoData"
    ws.append(["row_id", "amount", "note"])
    for i in range(1, rows + 1):
        ws.append([i, i * 10.5, f"row-{i}"])
    wb.save(path)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    corrupt = FIXTURES_DIR / "corrupt.xlsx"
    encoding_csv = FIXTURES_DIR / "encoding_latin1.csv"
    large = FIXTURES_DIR / "large_chunk_demo.xlsx"

    write_corrupt_xlsx(corrupt)
    write_encoding_latin1_csv(encoding_csv)
    write_large_chunk_demo_xlsx(large, rows=6000)

    print(f"Wrote {corrupt}")
    print(f"Wrote {encoding_csv}")
    print(f"Wrote {large}")


if __name__ == "__main__":
    main()
