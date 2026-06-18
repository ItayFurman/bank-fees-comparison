"""
חילוץ עמלות מקבצי Excel של תעריפוני בנקים — column-aware.

לפי כללי הבנקאות, בנק מחויב לפרסם תעריפון גם כקובץ Excel, ורובם
משתמשים בתבנית הסטנדרטית של בנק ישראל:
    מספר הסעיף | שירות | גובה העמלה (סכום/שיעור) | מינימום | מקסימום |
    מועד גביה | הוצאות נוספות | הערות

המודול מזהה את שורת-הכותרת בכל טבלה, ממפה את העמודות לפי משמעותן,
ומחלץ כל עמלה כשורה מובנית (קוד, שם, מחיר, מינ', מקס', הערות).
כך לא "נבלעים" מחירים ולא מתערבבים סף-עסקה/מינימום עם המחיר עצמו.

כשאין כותרת מזוהה (גיליונות חופשיים) — נופלים ל-heuristic גנרי.
גיליונות הטבות/מצומצם מסומנים tier=1 כדי שלא יִדרסו את התעריף הראשי.
"""
from __future__ import annotations
import re
from pathlib import Path

import pandas as pd

from .extractor import RawRow


# ============================================================================
# קריאת Excel
# ============================================================================

def _read_excel_all_sheets(path: str | Path) -> dict[str, pd.DataFrame]:
    """קורא את כל הגיליונות. מחזיר {sheet_name: df}. מטפל ב-xls וב-xlsx."""
    path = str(path)
    last_err: Exception | None = None
    for eng in (None, "openpyxl", "xlrd"):
        try:
            return pd.read_excel(path, sheet_name=None, header=None,
                                 dtype=str, engine=eng)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise last_err  # type: ignore[misc]


# ============================================================================
# עזרי טקסט / regex
# ============================================================================

_HEB_RE = re.compile(r"[֐-׿]")
_PRICE_RE = re.compile(r"\d+[.,]?\d*\s*(?:₪|ש[\"׳']?ח|%|\$|USD|ILS|דולר|אירו|אחוז)")
_PRICE_BARE_RE = re.compile(r"^\s*\d+[.,]?\d*\s*$")
# מספר בראש התא ואחריו מילת-יחידה עברית: "1.20 לפעולה", "6.3 בפיקוח", "30.0 לחודש"
_PRICE_LEAD_RE = re.compile(r"^\s*\d+[.,]?\d*\s*%?\s*[א-ת(]")
_CODE_RE = re.compile(r"^\(?\s*(?:\d+(?:\.\d+){0,3}|[א-ת])\s*\)?$")
# פטור/ללא-עמלה — ערך לגיטימי בעמודת המחיר אף שאין בו ספרה
_EXEMPT_RE = re.compile(r"פטור|ללא עמלה|ללא תשלום|אין עמלה|כלול|חינם|ל\s*ל\s*א")


def _norm(s) -> str:
    """נרמול תא: NBSP→רווח, כיווץ רווחים/שורות, סינון 'nan'."""
    if s is None:
        return ""
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return "" if s.lower() == "nan" else s


def _is_hebrew(cell: str) -> bool:
    return bool(cell and _HEB_RE.search(cell))


def _looks_like_price(cell: str) -> bool:
    if not cell:
        return False
    cell = cell.strip()
    return bool(_PRICE_RE.search(cell) or _PRICE_BARE_RE.match(cell)
                or _PRICE_LEAD_RE.match(cell))


def _amount_has_value(cell: str) -> bool:
    """
    בדיקה רכה לעמודת-מחיר ידועה: די בכך שיש ספרה (מחיר בכל פורמט)
    או מילת-פטור. כך לא מפספסים "1.20 לפעולה (בפיקוח)" / "6.3 בפיקוח".
    """
    if not cell:
        return False
    if re.search(r"\d", cell):
        return True
    return bool(_EXEMPT_RE.search(cell))


def _looks_like_code(cell: str) -> bool:
    return bool(cell and _CODE_RE.match(cell.strip()))


# שורות-גבול/שירות פנימי של התבנית — לא עמלות
_BOUNDARY = (
    "תחילת טבלה", "סוף טבלה", "תחילת מידע", "סוף מידע",
    "גבול צד שמאל", "גבול תחתון", "גבול עליון", "גבול ימני", "גבול",
)
# כותרות עמודה — אם תא שווה לאחת מאלה, זו שורת-כותרת ולא עמלה
_HEADER_WORDS = (
    "שירות", "השירות", "שם עמלה", "שם העמלה", "שם השירות", "מספר",
    "גובה העמלה", "גובה ההוצאה", "סכום", "שיעור", "מינימום", "מקסימום",
    "מועד גביה", "מועד הגביה", "הוצאות נוספות", "הערות", "מחיר",
)


def _is_boundary(cell: str) -> bool:
    c = cell.strip()
    return any(c.startswith(b) for b in _BOUNDARY)


def _is_header_word(cell: str) -> bool:
    return cell.strip() in _HEADER_WORDS


def _is_disclaimer(cell: str) -> bool:
    c = cell.strip()
    return (c.startswith("לידיעתך") or c.startswith("* ")
            or c.startswith("ככל שהעמלה") or c.startswith("(*)"))


# ============================================================================
# מיפוי עמודות לפי שורת-כותרת
# ============================================================================

def _is_name_header(h: str) -> bool:
    h = h.strip()
    # FIBI/בינ"ל/מסד: "תאור העמלה" ; יהב: "תיאור הפעולה"
    if h.startswith("תאור") or h.startswith("תיאור"):
        return True
    if h in ("שירות", "השירות"):
        return True
    return ("שם עמלה" in h or "שם השירות" in h or "שם הפעולה" in h)


def _amount_score(h: str) -> int:
    """ככל שגבוה יותר — סיכוי גבוה יותר שזו עמודת המחיר הראשי."""
    h = h.replace("\n", " ")
    if "גובה העמלה" in h or "גובה ההוצאה" in h:
        return 6
    if "סכום/שיעור" in h or "סכום /שיעור" in h or "סכום/ שיעור" in h:
        return 5
    if h.strip() == "מחיר":
        return 5
    if "הטבה/מחיר" in h or "מחיר/הטבה" in h:
        return 4
    if h.strip() == "שיעור":
        return 4
    if "תעריף" in h:
        return 4
    if h.strip() == "סכום לתשלום":
        return 3
    if h.strip() == "סכום":
        return 2
    if "הטבה" in h:
        return 2
    return 0


def _map_columns(cells: list[str]) -> dict[str, int] | None:
    """ממפה שורת-כותרת ל-{name, amount, min, max, notes, code}. None אם לא כותרת."""
    name_col = amount_col = min_col = max_col = notes_col = code_col = None
    best_amt = 0
    for i, raw in enumerate(cells):
        h = _norm(raw)
        if not h:
            continue
        if name_col is None and _is_name_header(h):
            name_col = i
        sc = _amount_score(h)
        if sc > best_amt:
            best_amt, amount_col = sc, i
        if min_col is None and ("מינימום" in h or h.startswith("מינ")
                                or "מיזער" in h):  # מזרחי: "מיזערי"
            min_col = i
        if max_col is None and ("מקסימום" in h or h.startswith("מקס")
                                or "מירב" in h):    # מזרחי: "מירבי"
            max_col = i
        if notes_col is None and ("הערות" in h or "מידע נוסף" in h):
            notes_col = i
        if code_col is None and ("מספר" in h or h.strip() == "סעיף"
                                 or "הסעיף" in h):
            code_col = i
    if name_col is not None and amount_col is not None and name_col != amount_col:
        m = {"name": name_col, "amount": amount_col}
        if min_col is not None:
            m["min"] = min_col
        if max_col is not None:
            m["max"] = max_col
        if notes_col is not None:
            m["notes"] = notes_col
        if code_col is not None:
            m["code"] = code_col
        return m
    return None


def _cell(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return _norm(cells[idx])


def _find_code_in_row(cells: list[str], mapping: dict[str, int]) -> str:
    """נסיגה: קוד סעיף רק כשאין עמודת-קוד ממופה. מדלגים על עמודות
    מחיר/מינ'/מקס'/הערות/שם כדי שמחיר ('12.6') או הפניית-הערה ('08')
    לא ייחשבו בטעות כקוד סעיף. מעדיפים קוד היררכי עם נקודה ('1.2.1')
    על פני הפניית-הערה בודדת ('(2)')."""
    skip = {mapping.get(k) for k in ("amount", "min", "max", "notes", "name")}
    dotted = ""
    plain = ""
    for i, c in enumerate(cells):
        if i in skip:
            continue
        cc = _norm(c)
        if _looks_like_code(cc) and re.search(r"\d", cc):
            if "." in cc and not dotted:
                dotted = cc
            elif not plain:
                plain = cc
    return dotted or plain


# ============================================================================
# חילוץ מובנה (sheet עם כותרת תבנית)
# ============================================================================

_SECONDARY_CAT_RE = re.compile(r"נספח|הטבו?ת|מצומצמ?ם|הנחה בדמי|מבצע")


def _category_is_secondary(text: str) -> bool:
    """קטע נספח/הטבות/מצומצם בתוך גיליון ראשי — תוכן משני (tier 1)."""
    return bool(text and _SECONDARY_CAT_RE.search(text))


def _extract_structured(df: pd.DataFrame, sheet_name: str,
                        tier: int) -> list[RawRow]:
    out: list[RawRow] = []
    current: dict[str, int] | None = None
    cat_name = ""   # שם שורת-הקטגוריה האחרונה (למשל "דמי כרטיס")
    cat_code = ""   # קוד שורת-הקטגוריה (למשל "6.1") — לזיהוי שורות-בת

    for idx, row in df.iterrows():
        cells = [_norm(c) for c in row.tolist()]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue

        # שורת-כותרת? עדכן מיפוי והמשך
        mapping = _map_columns(cells)
        if mapping is not None:
            current = mapping
            continue
        if current is None:
            continue

        name = _cell(cells, current.get("name"))
        amount = _cell(cells, current.get("amount"))
        mn = _cell(cells, current.get("min"))
        mx = _cell(cells, current.get("max"))
        notes = _cell(cells, current.get("notes"))
        code = _cell(cells, current.get("code")) or _find_code_in_row(cells, current)

        # בחירת-שם עמידה להסטת-עמודות: שם-העמלה הוא תא-העברית הקרוב ביותר
        # (האינדקס הגבוה ביותר) שמשמאל לעמודת-המחיר — כי ב-RTL שם-העמלה צמוד
        # לפני המחיר, ושברי-קטגוריה (כמו "עובר ושב") נמצאים רחוק משמאל.
        amt_idx = current.get("amount")
        if amt_idx is not None:
            for i in range(amt_idx - 1, -1, -1):
                c = _cell(cells, i)
                if (_is_hebrew(c) and len(_HEB_RE.findall(c)) >= 2
                        and not _looks_like_code(c) and not _is_header_word(c)
                        and not _is_boundary(c)):
                    name = c
                    break

        # דלג על גבולות/כותרות חוזרות/הסתייגויות
        if not name or _is_boundary(name) or _is_header_word(name) \
                or _is_disclaimer(name):
            continue
        if not _is_hebrew(name) or len(name) < 3:
            continue

        has_price = _amount_has_value(amount) or _amount_has_value(mn) \
            or _amount_has_value(mx)
        if not has_price:
            # שורת-קטגוריה (שם בלבד, בלי מחיר) — שמור כהקשר, לא כעמלה
            if len(name) < 80 and not amount:
                cat_name = name
                cat_code = code
            continue

        # אם שם-העמלה הוא שורת-בת של קטגוריה (קוד 6.1.1 תחת 6.1) — נצרף את
        # שם הקטגוריה ("דמי כרטיס") לתווית, כי שם-העמלה הרשמי חי בשורת-האם.
        label = name
        if cat_name and cat_code and code and code.startswith(cat_code + "."):
            label = f"{cat_name} | {name}"

        section = f"{sheet_name} / {cat_name}" if cat_name else sheet_name
        eff_tier = max(tier, 1) if _category_is_secondary(cat_name) else tier
        out.append(RawRow(
            label=label[:300],
            value=amount[:200] if amount else (mn or mx)[:200],
            page=int(idx) + 1 if isinstance(idx, int) else 1,
            section_hint=section[:80],
            code=code[:20],
            min_text=mn[:60],
            max_text=mx[:60],
            notes_text=notes[:200],
            tier=eff_tier,
        ))
    return out


# ============================================================================
# חילוץ גנרי (fallback — גיליון בלי כותרת תבנית)
# ============================================================================

def _extract_generic(df: pd.DataFrame, sheet_name: str,
                     tier: int) -> list[RawRow]:
    out: list[RawRow] = []
    if df.empty:
        return out

    for idx, row in df.iterrows():
        cells = [_norm(c) for c in row.tolist()]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue
        # דלג על שורות גבול/כותרת/הסתייגות
        if any(_is_boundary(c) for c in cells):
            continue
        if all(_is_header_word(c) or _is_boundary(c) for c in cells):
            continue

        heb_cells = [c for c in cells if _is_hebrew(c)
                     and not _is_header_word(c) and not _is_disclaimer(c)]
        price_cells = [c for c in cells if _looks_like_price(c)]
        if not heb_cells or not price_cells:
            continue

        label = " | ".join(heb_cells)
        if len(label) < 5 or _is_disclaimer(label):
            continue
        # value = תאי-מחיר שאינם זהים לתווית
        value = " | ".join(price_cells)
        out.append(RawRow(
            label=label[:300],
            value=value[:200],
            page=int(idx) + 1 if isinstance(idx, int) else 1,
            section_hint=sheet_name[:80],
            tier=tier,
        ))
    return out


# ============================================================================
# סיווג גיליונות
# ============================================================================

def _sheet_tier(name: str) -> int | None:
    """0=תעריף ראשי, 1=נספח/מצומצם (עדיפות נמוכה), None=לדלג לגמרי."""
    n = name.strip()
    if "תוכן" in n or "ימי ערך" in n:
        return None
    if "מצומצם" in n or "מצומצמם" in n or "הטבות" in n:
        return 1
    # נספח א' (הטבות לאוכלוסיות) / נספח ה' (הטבות בערוצים) — משניים
    if re.match(r"^נספח\s*[אה]\b", n) or re.match(r"^נספח\s*[אה]['׳\s\-]", n):
        return 1
    return 0


def _has_header_anywhere(df: pd.DataFrame) -> bool:
    for _, row in df.iterrows():
        cells = [_norm(c) for c in row.tolist()]
        if _map_columns(cells) is not None:
            return True
    return False


# ============================================================================
# API ראשי
# ============================================================================

def extract_excel_rows(path: str | Path) -> list[RawRow]:
    """מחלץ שורות מקובץ Excel של תעריפון. מחזיר list[RawRow]."""
    sheets = _read_excel_all_sheets(path)
    out: list[RawRow] = []
    for name, df in sheets.items():
        tier = _sheet_tier(name)
        if tier is None:
            continue
        df = df.fillna("")
        if _has_header_anywhere(df):
            rows = _extract_structured(df, name, tier)
            if not rows:  # רשת ביטחון
                rows = _extract_generic(df, name, tier)
        else:
            rows = _extract_generic(df, name, tier)
        out.extend(rows)
    return out


# ============================================================================
# מיזוג PDF + Excel
# ============================================================================

def merge_extractions(pdf_rows: list[RawRow],
                      excel_rows: list[RawRow]) -> list[RawRow]:
    """
    משלב Excel (אמין) + PDF (משלים). Excel תמיד נכנס; שורות PDF מתווספות
    רק אם אינן חופפות (≥50% חפיפת מילים) לשורת Excel קיימת.
    """
    if not excel_rows:
        return pdf_rows
    if not pdf_rows:
        return excel_rows

    out = list(excel_rows)
    excel_signatures = []
    for er in excel_rows:
        words = set(re.findall(r"\w{3,}", er.label))
        if words:
            excel_signatures.append(words)

    for pr in pdf_rows:
        pr_words = set(re.findall(r"\w{3,}", pr.label))
        if not pr_words:
            continue
        is_dup = any(
            len(pr_words & sig) / max(len(pr_words), 1) >= 0.5
            for sig in excel_signatures
        )
        if not is_dup:
            out.append(pr)
    return out


def detect_excel_file(pdf_path: str | Path, excel_dir: str | Path) -> Path | None:
    """מחפש קובץ Excel תואם ל-PDF נתון (לפי stem)."""
    pdf_path = Path(pdf_path)
    excel_dir = Path(excel_dir)
    if not excel_dir.exists():
        return None
    stem = pdf_path.stem.lower()
    for ext in (".xlsx", ".xls"):
        candidate = excel_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    for f in excel_dir.glob("*.xls*"):
        if stem in f.stem.lower() or f.stem.lower() in stem:
            return f
    return None
