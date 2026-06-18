"""
CLI להפעלת הפייפליין.

דוגמאות:
  python -m src.cli ingest                       # מעבד את כל ה-PDF בתיקיית pdfs/
  python -m src.cli compare leumi hapoalim       # טבלת השוואה ל-2 בנקים
  python -m src.cli compare leumi hapoalim --regulated   # רק עמלות בפיקוח
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import pandas as pd

from .extractor import extract_rows
from .normalizer import normalize, to_jsonable
from .bank_profiles import detect_bank, PROFILES_BY_ID
from .comparator import build_comparison, cheapest_per_fee

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
OUT_DIR = ROOT / "output"


def cmd_ingest(args):
    OUT_DIR.mkdir(exist_ok=True)
    pdfs = list(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"אין קבצי PDF ב-{PDF_DIR}. הנח שם תעריפונים ונסה שוב.", file=sys.stderr)
        return 1
    for p in pdfs:
        profile = detect_bank(p.name)
        if not profile:
            print(f"[skip] לא זוהה בנק עבור {p.name} (הוסף hint ב-bank_profiles.py)")
            continue
        print(f"[ingest] {profile.display_name}  <-  {p.name}")
        rows = extract_rows(p)
        normalized = normalize(rows)
        out_file = OUT_DIR / f"{profile.bank_id}.json"
        out_file.write_text(
            json.dumps({
                "bank_id": profile.bank_id,
                "display_name": profile.display_name,
                "source_file": p.name,
                "raw_row_count": len(rows),
                "fees": to_jsonable(normalized),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"          -> {len(normalized)} עמלות נורמלו, נשמר ב-{out_file.name}")
    return 0


def _load_bank(bank_id: str) -> dict:
    f = OUT_DIR / f"{bank_id}.json"
    if not f.exists():
        raise SystemExit(f"לא נמצא JSON עבור {bank_id}. הרץ קודם: python -m src.cli ingest")
    return json.loads(f.read_text(encoding="utf-8"))


def cmd_compare(args):
    from .normalizer import NormalizedFee
    by_bank = {}
    for bid in args.banks:
        if bid not in PROFILES_BY_ID:
            print(f"בנק לא מוכר: {bid}. אפשרויות: {', '.join(PROFILES_BY_ID)}", file=sys.stderr)
            return 1
        data = _load_bank(bid)
        by_bank[bid] = {k: NormalizedFee(**v) for k, v in data["fees"].items()}

    df = build_comparison(by_bank, only_regulated=args.regulated)
    bank_cols = [PROFILES_BY_ID[b].display_name for b in args.banks]
    df = cheapest_per_fee(df, bank_cols)

    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.max_colwidth", 40)
    print(df.to_string(index=False))

    if args.csv:
        out = OUT_DIR / args.csv
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\nנשמר: {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="bank-fee-compare")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="חלץ ונרמל את כל ה-PDFים בתיקיית pdfs/")

    c = sub.add_parser("compare", help="הצג טבלת השוואה")
    c.add_argument("banks", nargs="+", help="bank_id (לדוגמה: leumi hapoalim)")
    c.add_argument("--regulated", action="store_true", help="רק עמלות בפיקוח")
    c.add_argument("--csv", help="שמירת הפלט ל-CSV בשם זה בתוך output/")

    args = ap.parse_args()
    if args.cmd == "ingest":
        sys.exit(cmd_ingest(args))
    elif args.cmd == "compare":
        sys.exit(cmd_compare(args))


if __name__ == "__main__":
    main()
