"""
נרמול שורות גולמיות לסכמה הקנונית (כללי הבנקאות, נבו).

קלט:  list[RawRow] מה-extractor.
פלט:  dict[fee_key] -> NormalizedFee — אחיד בין בנקים.

תכונות חדשות לעומת v1:
1. שמירה של ההערות / תנאי המחיר (לא רק ערך מספרי).
2. סימון "חריגה" (deviation) כאשר תווית המקור לא תואמת בדיוק לשם הרשמי.
3. בחירה מושכלת של ההתאמה הטובה ביותר (highest_score) במקרה של מספר התאמות.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
import re

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

from .schema import FEE_KEYWORDS, FEE_BY_KEY
from .extractor import RawRow


@dataclass
class NormalizedFee:
    fee_key: str
    he_name: str                    # שם רשמי לפי כללי בנק ישראל
    code: str                       # קוד רשמי, למשל "1(א)(2)"
    part: str                       # חלק רשמי, למשל "חלק 1 - חשבון עו\"ש"
    regulated: bool
    price_value: float | None
    price_unit: str
    price_text: str
    notes: str
    source_label: str
    matched_keyword: str
    match_score: int
    deviation: str
    page: int


# --- ניתוח מחיר ----------------------------------------------------------------

_NUM_RE = re.compile(r"(\d+[.,]?\d*)")
_PERCENT_RE = re.compile(r"(\d+[.,]?\d*)\s*%")
_MIN_RE = re.compile(r"מינ['׳\.\"]?(?:ימום)?\s*[:\-]?\s*([\d.,]+)")
_MAX_RE = re.compile(r"מ(?:כסימום|קסימום|קס')\s*[:\-]?\s*([\d.,]+)")
_EXEMPT_RE = re.compile(r"(פטור|חינם|ללא תשלום|ללא עמלה|אין עמלה)")
_HEB_N = re.compile(r"[֐-׿]")
# שורת-הפנייה ("ראה נספח" / "לפי סוג כרטיס") — אין בה מחיר אמיתי, רק הפניה.
# נחזיר None כדי שלא ניקח מספר-הערה/מספר-נספח כמחיר, ושורת-המחיר האמיתית תנצח.
_REF_RE = re.compile(
    r"ראה\s*נספח|ראה\s*בנספח|מפורט\s*בנספח|מפורט\s*בטבלה|"
    r"לפי\s*סוג|ראה\s*טבלה|בהתאם\s*לנספח|ראה\s*פירוט"
)
# טקסט משובש מחילוץ PDF (עברית שהתהפכה — RTL/LTR) מייצר מספרים שאינם המחיר.
# מילים נפוצות בטבלאות-מזומן כשהן הפוכות: "שטרות"->"תורטש", "מטבעות"->"תועבטמ".
# הופעתן היא חתימה ודאית-כמעט לשורה משובשת -> המחיר אינו אמין.
_MOJIBAKE_RE = re.compile(r"תורטש|תועבטמ|ועבטמ|תוטורפ")

# שורות שאלה לא תעריפי-עמלות אמיתיים אלא טבלאות הטבה/הנחה/בונוסים -
# נדחה אותן מההתאמה כדי לא לחלץ "100% הנחה" כאילו זה תעריף
# מילים שמסמנות שורת הטבה/הנחה - בכל סדר תווים (מקבל artifacts של RTL עם רווחים)
_DISCOUNT_RE = re.compile(
    r"ה\s*נ\s*ח\s*ה"        # "הנחה" עם רווחים אופציונליים
    r"|ה\s*ט\s*ב\s*ה"        # "הטבה"
    r"|ז\s*י\s*כ\s*ו\s*י"    # "זיכוי"
    r"|ה\s*ק\s*ל\s*ה"        # "הקלה"
    r"|ב\s*ו\s*נ\s*ו\s*ס"    # "בונוס"
    r"|מהמחיר|מהתעריף|פטור\s*מ\d"
)


# ----- הבחנה בין "סף עסקה" לבין "מחיר עמלה" ------------------------------------
# מילים שמקדימות מספר והופכות אותו לסכום-העסקה / סף — ולא למחיר העמלה עצמה.
# דוגמה: "הלוואות מעל 100,000 ש\"ח" → 100,000 הוא סף, לא מחיר!
# דוגמה: "העברה עד 1,000,000 ש\"ח" → 1,000,000 הוא תקרת העסקה, לא מחיר!
_THRESHOLD_END = re.compile(
    r"(?:מעל|עד\s*ל?|לפחות|בסך|בסכום\s*של|"
    r"לא\s*יותר\s*מ-?|לא\s*פחות\s*מ-?|יותר\s*מ-?|פחות\s*מ-?|מ-)\s*$"
)
# מילים שמקדימות מספר ומסמנות רצפה/תקרה (מינימום/מקסימום) —
# לא המחיר ה"ראשי", אך עשוי לשמש כמחיר אם אין ערך אחר.
_BOUND_END = re.compile(
    r"(?:מינימום|מקסימום|מקסימאלי|מינימאלי|מינ['׳\.]|מקס['׳\.])\s*$"
)

# מספר עם מטבע — שני הכיוונים: "5.5 ₪" וגם "₪ 5.5"
_SHEKEL_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(?:₪|ש[\"׳']?ח|ILS\b)")
_NUM_SHEKEL = re.compile(r"(?:₪|ש[\"׳']?ח|ILS\b)\s*(\d+(?:\.\d+)?)")
_PCT_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*%")
# הקשר "הנחה/הטבה" שמבטל אחוז כעמלה אמיתית
_DISCOUNT_AFTER = re.compile(r"^\s*(?:ה\s*נ\s*ח\s*ה|ה\s*ט\s*ב\s*ה|זיכוי|הקלה)")
_DISCOUNT_BEFORE = re.compile(r"(?:הנחה|הטבה|זיכוי|הקלה|בונוס)\s*(?:של\s*)?$")


def _first_headline_percent(text: str) -> float | None:
    """אחוז 'ראשי' אמיתי — לא הנחה/הטבה ולא תקרת 'לא יותר מ-X%'."""
    for m in _PCT_NUM.finditer(text):
        before = text[:m.start()]
        after = text[m.end():m.end() + 12]
        if _DISCOUNT_AFTER.search(after) or _DISCOUNT_BEFORE.search(before):
            continue
        if _THRESHOLD_END.search(before):      # "לא יותר מ-27%" — תקרה, לא מחיר
            continue
        try:
            return float(m.group(1))
        except ValueError:
            continue
    return None


def _first_headline_shekel(text: str) -> float | None:
    """ערך בש\"ח שאינו סף-עסקה ואינו רצפת/תקרת מינ'/מקס'."""
    for rx in (_SHEKEL_NUM, _NUM_SHEKEL):
        for m in rx.finditer(text):
            before = text[:m.start()]
            if _THRESHOLD_END.search(before) or _BOUND_END.search(before):
                continue
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _parse_price(value_text: str, label_text: str = "") -> tuple[float | None, str]:
    """
    מחזיר (ערך, יחידה). סדר עדיפויות מתוקן כדי לא לבלבל סף-עסקה עם מחיר:
      1. אחוז ראשי אמיתי   ("0.4% מינימום 26 ש\"ח" → 0.4%, ולא 26).
      2. ערך בש\"ח שאינו סף ("מעל 100,000 ש\"ח") ואינו מינ'/מקס'.
      3. פטור/חינם (גם אם מופיע רק בתווית) → 0.
      4. fallback: המספר הראשון שאינו צמוד למילת-סף ("מעל/עד").
    """
    if not value_text and not label_text:
        return None, "ILS"
    text = (value_text or "").replace(",", "")

    p = _first_headline_percent(text)
    if p is not None:
        return p, "percent"

    s = _first_headline_shekel(text)
    if s is not None:
        return s, "ILS"

    if _EXEMPT_RE.search(value_text or "") or _EXEMPT_RE.search(label_text or ""):
        return 0.0, "ILS"

    # שורת-הפניה ("ראה נספח ד' (1)", "לפי סוג כרטיס") אינה מחיר —
    # אחרת מספר-הנספח/הערה נתפס בטעות כמחיר (למשל 1.0 לדמי כרטיס).
    if _REF_RE.search(value_text or "") or _REF_RE.search(label_text or ""):
        return None, "ILS"

    # fallback — מספר ראשון שאינו צמוד למילת-סף
    for m in _NUM_RE.finditer(text):
        before = text[:m.start()]
        if _THRESHOLD_END.search(before):
            continue
        try:
            return float(m.group(1)), "ILS"
        except ValueError:
            continue
    return None, "ILS"


def _bound_note(text: str) -> str:
    """ערך מינ'/מקס' מעמודה ייעודית — רק אם יש בו ספרה."""
    t = (text or "").strip()
    return t[:22] if re.search(r"\d", t) else ""


def _extract_notes(value_text: str, label_text: str,
                   min_text: str = "", max_text: str = "",
                   notes_text: str = "") -> str:
    """מחלץ הערות: מינ'/מקס' (קודם מעמודות ייעודיות, אחרת regex),
    פטור, יחידת-תמחור, ומחיר-משני/ערוץ מעמודת ההערות."""
    notes_parts: list[str] = []
    txt = f"{value_text} | {label_text}"

    if _EXEMPT_RE.search(value_text):
        notes_parts.append("פטור/חינם")

    # מינ'/מקס' — עמודות ייעודיות אמינות יותר; נסיגה ל-regex על הטקסט
    mn = _bound_note(min_text)
    mx = _bound_note(max_text)
    if not mn:
        m_min = _MIN_RE.search(txt)
        mn = m_min.group(1) if m_min else ""
    if not mx:
        m_max = _MAX_RE.search(txt)
        mx = m_max.group(1) if m_max else ""
    if mn:
        notes_parts.append(f"מינ' {mn}")
    if mx:
        notes_parts.append(f"מקס' {mx}")

    # מחיר-משני/תנאי מעמודת ההערות (רק אם יש טקסט עברי — לא הפניות-הערה)
    nt = (notes_text or "").strip()
    if nt and _HEB_N.search(nt) and len(nt) > 4:
        notes_parts.append(nt[:50])

    # מילים שמשפיעות על התעריף
    for kw, label in [
        ("בפיקוח",      "בפיקוח"),
        ("לפעולה",      "לפעולה"),
        ("לחודש",       "לחודש"),
        ("לרבעון",      "לרבעון"),
        ("לשנה",        "לשנה"),
        ("לרביע",       "לרבעון"),
        ("לשיק",        "לשיק"),
        ("לעמוד",       "לעמוד"),
        ("לבקשה",       "לבקשה"),
        ("בערוץ ישיר",  "בערוץ ישיר"),
        ("ע\"י פקיד",   "ע\"י פקיד"),
        ("אינטרנט",     "אינטרנט"),
        ("דיגיטל",      "דיגיטלי"),
    ]:
        if kw in txt and label not in notes_parts:
            notes_parts.append(label)

    return " · ".join(notes_parts[:6])


# --- התאמה לעמלות הקנוניות ----------------------------------------------------

def _score(label: str, keyword: str) -> int:
    if keyword in label:
        return 100
    if fuzz is None:
        return 0
    return int(fuzz.partial_ratio(keyword, label))


def _best_match(label: str) -> tuple[str, str, int] | None:
    """מחזיר (fee_key, matched_keyword, score) הטוב ביותר, או None."""
    best: tuple[str, str, int] | None = None
    for fee_key, keywords in FEE_KEYWORDS.items():
        for kw in keywords:
            s = _score(label, kw)
            if best is None or s > best[2]:
                best = (fee_key, kw, s)
    return best


def _detect_deviation(label: str, matched_kw: str, score: int) -> str:
    """מחזיר טקסט חריגה אם השם השונה מהותית. ריק אם תקין."""
    if score >= 95:
        return ""
    # ההתאמה נמצאה אך השם המקורי לא בדיוק רשמי
    snippet = label.replace("\n", " ").strip()[:60]
    if score < 80:
        return f"⚠ שם שונה / לא רשמי: \"{snippet}\""
    return f"שם שונה: \"{snippet}\""


# --- API ראשי ----------------------------------------------------------------

def _is_discount_row(value_text: str) -> bool:
    """
    זיהוי שורת הטבה/הנחה (לא תעריף אמיתי) — למשל "100% הנחה" בטבלת הטבות.
    """
    if not value_text:
        return False
    # שורה שכל המספרים בה מלווים ב"הנחה"/"הטבה" — דחה
    if _DISCOUNT_RE.search(value_text):
        # אם אין מספר אחד עם ₪ או "ש"ח" - בוודאות זו שורת הנחה
        has_ils = bool(re.search(r"\d+[.,]?\d*\s*(?:₪|ש[\"׳']?ח|ILS|דולר|\$)", value_text))
        if not has_ils:
            return True
    return False


# סף 85: מתחת לכך partial_ratio מתאים מילה משותפת בודדת בין עמלות שונות
# (למשל "דמי כרטיס" ↔ "דמי טיפול בחילוט ערבות") ומייצר התאמות-שווא.
def normalize(rows: list[RawRow], threshold: int = 85) -> dict[str, NormalizedFee]:
    out: dict[str, NormalizedFee] = {}
    best_rank: dict[str, tuple] = {}
    for r in rows:
        m = _best_match(r.label)
        if not m or m[2] < threshold:
            continue
        fee_key, matched_kw, score = m

        # שורת-קצה קצרה מדי (< 5 תווי-תוכן) שהותאמה רק בפאזי ואינה תת-סעיף עם מקף —
        # רעש (למשל "בנקט" שהותאם ל"שינוי שעבודים בבנק"). תת-סעיף "- בבנק" נשמר.
        if score < 100:
            _stripped = re.sub(r"[\s\"'׳״().,\[\]\-–•]", "", r.label or "")
            if len(_stripped) < 5 and not (r.label or "").lstrip().startswith(("-", "–", "•")):
                continue

        # דחיית שורות הטבה/הנחה — לא תעריף אמיתי
        if _is_discount_row(r.value):
            continue

        fee_def = FEE_BY_KEY[fee_key]
        price, unit = _parse_price(r.value, r.label)

        # טקסט משובש (עברית הפוכה בחילוץ PDF): המספרים בשורה אינם המחיר האמיתי.
        # מאפסים את המחיר *לפני* הדירוג כדי ששורה נקייה (אם קיימת) תנצח, ומסמנים לבדיקה.
        _mojibake = bool(_MOJIBAKE_RE.search(r.value or "") or
                         _MOJIBAKE_RE.search(r.label or ""))
        if _mojibake:
            price, unit = None, None

        # דירוג המועמד: תעריף ראשי (tier 0) תמיד מנצח נספח/הטבות (tier 1);
        # אחר-כך עדיפות לשורה עם מחיר, ואז ציון-התאמה גבוה, ואז קוד-סעיף.
        # כך מחיר אמיתי מהתעריף לא נדרס ע"י שורת-נספח בעלת ציון מקרי גבוה יותר.
        rank = (
            1 if r.tier == 0 else 0,
            1 if price is not None else 0,
            score,
            1 if r.code else 0,
        )
        if fee_key in out and best_rank.get(fee_key, ()) >= rank:
            continue

        notes = _extract_notes(r.value, r.label, r.min_text, r.max_text,
                               r.notes_text)
        deviation = _detect_deviation(r.label, matched_kw, score)
        if _mojibake:
            deviation = ("⚠ טקסט משובש בתעריפון (עברית הפוכה בחילוץ) — "
                         "המחיר לא חולץ אוטומטית; נדרשת בדיקה ידנית")

        # אמון בחילוץ: אם זיהינו ערך ב-₪ באופן מפורש - לא נכפה "percent" מהסכמה.
        # היחידה מהסכמה תשמש רק כ-fallback כשלא הצלחנו לזהות יחידה.
        final_unit = unit if unit else fee_def.unit

        out[fee_key] = NormalizedFee(
            fee_key=fee_key,
            he_name=fee_def.he_name,
            code=fee_def.code,
            part=fee_def.part,
            regulated=fee_def.regulated,
            price_value=price,
            price_unit=final_unit,
            price_text=r.value.replace("\n", " ").strip()[:120],
            notes=notes,
            source_label=r.label.replace("\n", " ").strip()[:120],
            matched_keyword=matched_kw,
            match_score=score,
            deviation=deviation,
            page=r.page,
        )
        best_rank[fee_key] = rank
    return out


def to_jsonable(normalized: dict[str, NormalizedFee]) -> dict[str, dict]:
    return {k: asdict(v) for k, v in normalized.items()}


def collect_unmatched(rows: list[RawRow], threshold: int = 85) -> list[dict]:
    """
    מחזיר שורות שלא הותאמו לאף עמלה קנונית — קלט לסוכן (R1/R4):
    חשד לשירות חדש שלא קיים בכללי העמלות / שהוסף לחלק 9 ללא אישור.
    מסנן רק שורות עם signal גבוה (טקסט עברי + מחיר/אחוז).
    """
    import re
    out = []
    seen = set()
    for r in rows:
        m = _best_match(r.label)
        if m and m[2] >= threshold:
            continue
        # signal: ערך מספרי או % או "ש"ח"
        if not re.search(r"\d", r.value or ""):
            continue
        label = r.label.replace("\n", " ").strip()[:120]
        if not label or len(label) < 8 or label in seen:
            continue
        seen.add(label)
        out.append({
            "label": label,
            "value": (r.value or "").replace("\n", " ").strip()[:80],
            "page": r.page,
            "best_keyword_score": m[2] if m else 0,
        })
    # החזר רק את אלה עם הסיגנל הכי גבוה (כדי לא להציף)
    return out[:30]
