"""
מנוע חילוץ PDF רב-מנועי עם ציון איכות אוטומטי.

Logic:
  • לכל עמוד מנסה pdfplumber + pymupdf + cp1255-decoded variant.
  • מודד את "ציון האיכות": יחס תווי עברית, מספר (cid:..), אורך טקסט.
  • בוחר את הפלט עם הציון הגבוה ביותר.
  • שומר cache במקום (lru_cache) כדי לא לחזור על אותה עבודה.
"""
from __future__ import annotations
import re
import functools
from pathlib import Path
from typing import Iterator

import pdfplumber

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ============================================================================
# מדדי איכות
# ============================================================================

_HEB_RE = re.compile(r"[֐-׿]")
_CID_RE = re.compile(r"\(cid:\d+\)")
_LATIN_GIBBERISH_RE = re.compile(r"[ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]")


def evaluate_text_quality(text: str) -> float:
    """
    מחזיר ציון 0-100 לאיכות הטקסט.
    100 = טקסט עברי תקין. 0 = ג'יבריש מוחלט.
    """
    if not text or len(text) < 50:
        return 0.0
    total = len(text)
    heb = len(_HEB_RE.findall(text))
    cid = len(_CID_RE.findall(text))
    latin_garbage = len(_LATIN_GIBBERISH_RE.findall(text))
    # ספירת מילים סבירות באורך 2-15
    words = [w for w in text.split() if 2 <= len(w) <= 15]

    if cid > 5:
        return 5.0  # CID encoded - לא קריא
    if latin_garbage > total * 0.15:
        return 10.0  # latin-1 garbage

    # ציון בסיס לפי יחס עברית
    heb_ratio = heb / total
    score = heb_ratio * 100

    # בונוס על אורך מילים סביר
    if words and len(words) >= 10:
        score = min(100, score + 10)

    return score


def try_decode_as_cp1255(text: str) -> str | None:
    """
    מנסה לפענח טקסט שנראה כמו latin-1 ל-cp1255 (עברית).
    מחזיר None אם הניסיון לא משפר את האיכות.
    """
    try:
        decoded = text.encode("latin-1", errors="replace").decode(
            "windows-1255", errors="replace")
        # רק אם השיפור משמעותי
        if evaluate_text_quality(decoded) > evaluate_text_quality(text) + 30:
            return decoded
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return None


# ============================================================================
# מנועי חילוץ — לכל מנוע אותו ממשק
# ============================================================================

def _extract_with_pdfplumber(pdf_path: str) -> list[tuple[int, str, list]]:
    """
    מחזיר [(page_num, text, tables), ...] מ-pdfplumber.
    """
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            out.append((i, text, tables))
    return out


def _extract_with_pymupdf(pdf_path: str) -> list[tuple[int, str, list]]:
    """
    מחזיר [(page_num, text, tables), ...] מ-pymupdf (fitz).
    """
    if not HAS_FITZ:
        return []
    out = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            # pymupdf find_tables (זמין מ-fitz 1.23+)
            tables = []
            try:
                tf = page.find_tables()
                for tbl in tf:
                    tables.append(tbl.extract())
            except (AttributeError, Exception):
                pass
            out.append((i, text, tables))
    return out


# ============================================================================
# Best-engine selector
# ============================================================================

@functools.lru_cache(maxsize=32)
def extract_with_best_engine(pdf_path: str) -> tuple[list[tuple[int, str, list]], str]:
    """
    מחלץ עמודי PDF במנוע הטוב ביותר.

    מחזיר (pages, engine_name) — איפה pages = [(page_num, text, tables), ...]
    """
    pdf_path = str(Path(pdf_path).resolve())

    # נסיון 1: pdfplumber (default)
    try:
        pp_pages = _extract_with_pdfplumber(pdf_path)
        pp_score = _avg_quality([p[1] for p in pp_pages])
    except Exception:
        pp_pages, pp_score = [], 0.0

    # אם pdfplumber איכותי – נשתמש בו
    if pp_score >= 50:
        return pp_pages, "pdfplumber"

    # נסיון 2: pymupdf
    if HAS_FITZ:
        try:
            mu_pages = _extract_with_pymupdf(pdf_path)
            mu_score_raw = _avg_quality([p[1] for p in mu_pages])

            # אולי דרוש decode מ-latin-1 ל-cp1255
            mu_pages_decoded = []
            for page_num, text, tables in mu_pages:
                decoded = try_decode_as_cp1255(text)
                if decoded:
                    mu_pages_decoded.append((page_num, decoded, tables))
                else:
                    mu_pages_decoded.append((page_num, text, tables))
            mu_score_decoded = _avg_quality([p[1] for p in mu_pages_decoded])

            # בחר את הטוב ביותר
            if mu_score_decoded > max(pp_score, mu_score_raw):
                return mu_pages_decoded, "pymupdf+cp1255"
            if mu_score_raw > pp_score:
                return mu_pages, "pymupdf"
        except Exception:
            pass

    # ברירת מחדל — pdfplumber גם אם איכות ירודה
    return pp_pages, "pdfplumber (low quality)"


def _avg_quality(texts: list[str]) -> float:
    if not texts:
        return 0.0
    scores = [evaluate_text_quality(t) for t in texts]
    return sum(scores) / len(scores)
