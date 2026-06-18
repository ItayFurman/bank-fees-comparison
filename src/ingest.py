"""
Pipeline משולב — סורק PDF + Excel לכל בנק ומשלב את התוצאות.

לכל בנק:
  1. נסה לחלץ מ-PDF (אם קיים ב-pdfs/)
  2. נסה לחלץ מ-Excel (אם קיים ב-excel/)
  3. מזג את התוצאות — Excel קודם (אמין יותר), PDF משלים פערים
  4. נרמל לסכמה הקנונית
  5. שמור JSON ב-output/
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass

from .extractor import extract_rows, extract_with_engine_info, RawRow
from .excel_extractor import extract_excel_rows, merge_extractions, detect_excel_file
from .normalizer import normalize, to_jsonable, collect_unmatched, NormalizedFee
from .bank_profiles import detect_bank, BankProfile

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
EXCEL_DIR = ROOT / "excel"
OUT_DIR = ROOT / "output"


@dataclass
class IngestResult:
    bank_id: str
    display_name: str
    pdf_file: str | None
    excel_file: str | None
    pdf_rows: int
    excel_rows: int
    total_rows: int
    matched_fees: int
    pdf_quality: float
    pdf_engine: str
    source_summary: str  # "PDF+Excel" / "Excel בלבד" / "PDF בלבד"


def _index_pdfs_by_bank() -> dict[str, Path]:
    """מחזיר {bank_id: pdf_path} לכל PDF בתיקיית pdfs/."""
    out = {}
    for f in PDF_DIR.glob("*.pdf"):
        prof = detect_bank(f.name)
        if prof:
            out[prof.bank_id] = f
    return out


def _index_excels_by_bank() -> dict[str, Path]:
    """מחזיר {bank_id: excel_path} לכל Excel בתיקיית excel/."""
    out = {}
    if not EXCEL_DIR.exists():
        return out
    for f in EXCEL_DIR.glob("*.xls*"):
        prof = detect_bank(f.name)
        if prof:
            out[prof.bank_id] = f
    return out


def ingest_all() -> list[IngestResult]:
    """
    מריץ ingest על כל הבנקים — PDF + Excel — ומחזיר רשימת תוצאות.
    """
    OUT_DIR.mkdir(exist_ok=True)
    pdfs = _index_pdfs_by_bank()
    excels = _index_excels_by_bank()
    all_bank_ids = set(pdfs) | set(excels)

    results: list[IngestResult] = []

    for bank_id in all_bank_ids:
        from .bank_profiles import PROFILES_BY_ID
        prof = PROFILES_BY_ID.get(bank_id)
        if not prof:
            continue

        pdf_path = pdfs.get(bank_id)
        excel_path = excels.get(bank_id)

        # חלץ מ-PDF
        pdf_rows: list[RawRow] = []
        pdf_quality, pdf_engine = 0.0, "—"
        if pdf_path:
            try:
                pdf_rows, pdf_engine, pdf_quality = extract_with_engine_info(pdf_path)
            except Exception as e:
                print(f"PDF error for {bank_id}: {e}")

        # חלץ מ-Excel
        excel_rows: list[RawRow] = []
        if excel_path:
            try:
                excel_rows = extract_excel_rows(excel_path)
            except Exception as e:
                print(f"Excel error for {bank_id}: {e}")

        # מזג
        merged = merge_extractions(pdf_rows, excel_rows)

        # נרמל
        normalized = normalize(merged)
        unmatched = collect_unmatched(merged)

        # קבע סוג מקור
        if pdf_rows and excel_rows:
            source = "PDF+Excel"
        elif excel_rows:
            source = "Excel בלבד"
        elif pdf_rows:
            source = "PDF בלבד"
        else:
            source = "ללא נתון"

        # שמור JSON
        out_data = {
            "bank_id": bank_id,
            "display_name": prof.display_name,
            "source_file": pdf_path.name if pdf_path else None,
            "excel_file": excel_path.name if excel_path else None,
            "source_summary": source,
            "pdf_quality": pdf_quality,
            "pdf_engine": pdf_engine,
            "raw_row_count": len(merged),
            "pdf_row_count": len(pdf_rows),
            "excel_row_count": len(excel_rows),
            "fees": to_jsonable(normalized),
            "unmatched_high_signal": unmatched,
        }
        (OUT_DIR / f"{bank_id}.json").write_text(
            json.dumps(out_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        results.append(IngestResult(
            bank_id=bank_id,
            display_name=prof.display_name,
            pdf_file=pdf_path.name if pdf_path else None,
            excel_file=excel_path.name if excel_path else None,
            pdf_rows=len(pdf_rows),
            excel_rows=len(excel_rows),
            total_rows=len(merged),
            matched_fees=len(normalized),
            pdf_quality=pdf_quality,
            pdf_engine=pdf_engine,
            source_summary=source,
        ))

    # מיין לפי מספר עמלות מזוהות
    results.sort(key=lambda r: -r.matched_fees)
    return results


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    results = ingest_all()
    print(f"\n{'בנק':20s} {'מקור':14s} {'PDF':>5s} {'Excel':>6s} {'סה\"כ':>5s} {'עמלות':>6s}")
    print("-" * 75)
    for r in results:
        print(f"{r.display_name:20s} {r.source_summary:14s} "
              f"{r.pdf_rows:>5d} {r.excel_rows:>6d} "
              f"{r.total_rows:>5d} {r.matched_fees:>6d}")
    total = sum(r.matched_fees for r in results)
    print(f"\nסה\"כ עמלות מזוהות: {total}")
