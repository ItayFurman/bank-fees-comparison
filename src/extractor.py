"""
חילוץ טבלאות מתעריפוני בנקים (PDF) באמצעות pdfplumber.

המודול הזה אגנוסטי לבנק. הוא מחזיר רשימת RawRow גולמיות
(label, value, page, section_hint) ומשאיר את הזיהוי הסמנטי ל-normalizer.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import re

import pdfplumber
from .pdf_engines import extract_with_best_engine, evaluate_text_quality


@dataclass
class RawRow:
    label: str
    value: str
    page: int
    section_hint: str = ""
    # שדות מובנים (מאוכלסים ע"י חילוץ Excel column-aware; ריקים ב-PDF)
    code: str = ""            # קוד סעיף רשמי, למשל "1.2.1" / "(א)"
    min_text: str = ""        # עמודת מינימום
    max_text: str = ""        # עמודת מקסימום
    notes_text: str = ""      # עמודת הערות
    tier: int = 0             # 0 = תעריף ראשי, 1 = נספח/מצומצם (עדיפות נמוכה)

    def to_dict(self) -> dict:
        return asdict(self)


# טקסט עברי ב-pdfplumber לעיתים מגיע הפוך. אם רוב התווים בעברית, נהפוך.
_HEB_RE = re.compile(r"[֐-׿]")

def _maybe_reverse_rtl(s: str) -> str:
    """
    pdfplumber מחזיר טקסט עברי בסדר ויזואלי (מימין לשמאל) — שזה
    בפועל סדר הפוך לעומת הסדר הלוגי שאנו זקוקים לו.
    אנו הופכים גם את האותיות בתוך כל מילה וגם את סדר המילים בכל שורה,
    כדי שהטקסט יקרא כראוי.
    """
    if not s:
        return s
    heb = len(_HEB_RE.findall(s))
    if not (heb >= 3 and heb / max(len(s), 1) > 0.3):
        return s

    def fix_line(line: str) -> str:
        # הופכים תווים בתוך כל מילה רק אם היא בעברית, ואז הופכים סדר מילים
        words = [w[::-1] if _HEB_RE.search(w) else w for w in line.split(" ")]
        return " ".join(reversed(words))

    return "\n".join(fix_line(l) for l in s.split("\n"))


_PRICE_HINT = re.compile(r"(?:\d+[.,]?\d*\s*(?:₪|ש[\"']?ח|%|\bILS\b))|(?:^\s*\d+[.,]\d{2}\s*$)")


def _looks_like_price_cell(cell: str) -> bool:
    if not cell:
        return False
    return bool(_PRICE_HINT.search(cell)) or bool(re.fullmatch(r"\s*\d+[.,]?\d*\s*", cell))


def _row_to_label_value(row: list[str | None]) -> tuple[str, str] | None:
    """
    Heuristic: a fee table row typically has one long Hebrew label cell and
    one or more numeric cells. We collapse all non-price cells into the label
    and join the price cells into the value.
    """
    cells = [(_maybe_reverse_rtl((c or "").strip())) for c in row]
    cells = [c for c in cells if c]
    if len(cells) < 2:
        return None
    label_parts = [c for c in cells if not _looks_like_price_cell(c)]
    price_parts = [c for c in cells if _looks_like_price_cell(c)]
    if not label_parts or not price_parts:
        return None
    label = " | ".join(label_parts)
    value = " | ".join(price_parts)
    if len(label) < 3:
        return None
    return label, value


def extract_rows(pdf_path: str | Path) -> list[RawRow]:
    """
    חילוץ שורות מ-PDF במנוע הטוב ביותר.
    אם איכות הטקסט נמוכה - מחזיר רשימה ריקה (יחד עם רישום).
    """
    pdf_path = str(pdf_path)
    pages_data, engine = extract_with_best_engine(pdf_path)

    out: list[RawRow] = []
    for page_num, text, tables in pages_data:
        # כותרת קטע: שורת עברית קצרה בראש העמוד
        section_hint = ""
        for line in text.splitlines()[:3]:
            line = _maybe_reverse_rtl(line.strip())
            if _HEB_RE.search(line) and len(line) < 60:
                section_hint = line
                break

        # מסלול 1: טבלאות מובנות
        for tbl in tables:
            for row in tbl:
                lv = _row_to_label_value(row or [])
                if lv:
                    label, value = lv
                    out.append(RawRow(label=label, value=value,
                                      page=page_num, section_hint=section_hint))

        # מסלול 2 (fallback): קווי טקסט עם תיאור+מחיר
        if not tables:
            for line in text.splitlines():
                line = _maybe_reverse_rtl(line.strip())
                if not line or not _HEB_RE.search(line):
                    continue
                m = re.search(r"(.{6,}?)\s+([\d.,]+\s*(?:₪|%)?)\s*$", line)
                if m:
                    out.append(RawRow(label=m.group(1).strip(),
                                      value=m.group(2).strip(),
                                      page=page_num, section_hint=section_hint))
    return out


def extract_with_engine_info(pdf_path: str | Path) -> tuple[list[RawRow], str, float]:
    """
    כמו extract_rows, אבל מחזיר גם את שם המנוע ואת ציון האיכות.
    שימושי ל-UI שמראה למשתמש איזה PDF נקרא היטב ואיזה לא.
    """
    pdf_path = str(pdf_path)
    pages_data, engine = extract_with_best_engine(pdf_path)
    all_text = "\n".join(t for _, t, _ in pages_data)
    quality = evaluate_text_quality(all_text)
    rows = extract_rows(pdf_path)
    return rows, engine, quality
