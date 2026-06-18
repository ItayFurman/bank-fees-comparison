"""
Fingerprint every bank Excel: per sheet, report shape, whether it matches
the Bank-of-Israel standard template (header row containing 'שירות' and
'גובה העמלה'/'סכום'), and which sheets are benefit/condensed appendices.

Run:  python scripts/excel_fingerprint.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EXCEL_DIR = ROOT / "excel"

HEADER_HINTS = ("שירות", "גובה העמלה", "סכום", "שיעור")
SKIP_SHEET_HINTS = ("הטבות", "מצומצם", "מצומצמם", "ימי ערך", "לפי סוגים")


def header_row(df: pd.DataFrame) -> tuple[int, list[str]] | None:
    for idx, row in df.head(8).iterrows():
        cells = [str(c).strip() for c in row.tolist() if str(c).strip() not in ("", "nan")]
        joined = " ".join(cells)
        if "שירות" in joined and ("גובה העמלה" in joined or "סכום" in joined or "שיעור" in joined):
            return int(idx), cells
    return None


def main() -> int:
    files = sorted(EXCEL_DIR.glob("*.xls*"))
    for f in files:
        print(f"\n########## {f.name} ##########")
        try:
            sheets = pd.read_excel(f, sheet_name=None, header=None, dtype=str)
        except Exception as e:
            print(f"  ERROR reading: {type(e).__name__}: {e}")
            continue
        for name, df in sheets.items():
            df = df.fillna("")
            skip = any(h in name for h in SKIP_SHEET_HINTS)
            hr = header_row(df)
            tag = "STD-TEMPLATE" if hr else "simple/other"
            flag = "  [SKIP-appendix]" if skip else ""
            print(f"  {name[:42]:42s} shape={str(df.shape):>9s}  {tag}{flag}")
            if hr:
                idx, cells = hr
                print(f"      header@r{idx}: {cells}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
