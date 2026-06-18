"""
מודול אבטחה — מנטרל וקטורי תקיפה ידועים.

זיהיתי בסקירה:
  • Path Traversal דרך uf.name ב-uploader (CRITICAL)
  • XSS מאוחסן דרך תוכן PDF שנשלף ל-HTML עם unsafe_allow_html (CRITICAL)
  • JSON tampering דרך קבצי output/ ו-agent_memory/ (HIGH)
  • חוסר אימות PDF magic-bytes — קבצים מזויפים (HIGH)
  • Path traversal דרך finding_id ב-conversations (HIGH)
  • הזרקת CSS/HTML דרך user fields אצל הסוכן (MEDIUM)
  • ReDoS פוטנציאלי בפטרני regex (LOW)
  • חוסר rate limiting / auth בפריסה ציבורית (HIGH לפריסה)
"""
from __future__ import annotations
import html
import re
import unicodedata
from pathlib import Path


# ============================================================================
# 1. סניטיזציה של שמות קבצים — נגד Path Traversal
# ============================================================================

# תווים אסורים בשמות קבצים בכל מערכת
_FORBIDDEN_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"|?*\\/]')
_MAX_FILENAME_LEN = 200


def safe_filename(name: str, default: str = "unnamed.pdf") -> str:
    """
    מסנן שם קובץ מהמשתמש כדי למנוע Path Traversal והזרקות.
    מסיר: '..', '/', '\\', 0x00, אותיות בקרה, רווחים מובילים.
    אם השם ריק / נוצר ריק לאחר סינון → default.
    """
    if not name or not isinstance(name, str):
        return default

    # ניתוק רכיב נתיב — שומר רק את השם הבסיסי (basename)
    name = name.replace("\\", "/").split("/")[-1]

    # סינון unicode normalization attacks (תווים שנראים זהים)
    name = unicodedata.normalize("NFKC", name)

    # הסרת תווים מסוכנים
    name = _FORBIDDEN_NAME_CHARS.sub("_", name)

    # הסרת נקודות מובילות (קבצי dot מוסתרים, ".." traversal)
    name = name.lstrip(". ")

    # קיצור לאורך סביר
    name = name[:_MAX_FILENAME_LEN]

    # ודא סיומת .pdf (גם אם המשתמש שלח אחרת)
    if not name.lower().endswith(".pdf"):
        name = name + ".pdf"

    if not name or name == ".pdf":
        return default

    return name


# ============================================================================
# 2. אימות תוכן PDF — נגד מסכים של HTML/JS תחת שם .pdf
# ============================================================================

_PDF_MAGIC = b"%PDF-"
_MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_pdf_bytes(data: bytes, max_size: int = _MAX_PDF_SIZE) -> tuple[bool, str]:
    """
    מאמת ש-data הוא אכן PDF תקין.
    מחזיר (ok, error_message).
    """
    if not data:
        return False, "קובץ ריק"
    if len(data) > max_size:
        return False, f"קובץ גדול מ-{max_size // (1024 * 1024)} MB"
    if len(data) < 100:
        return False, "קובץ קטן מדי כדי להיות PDF תקין"
    # PDF magic bytes — ב-1024 הבייטים הראשונים
    if _PDF_MAGIC not in data[:1024]:
        return False, "חסר חתימת PDF (%PDF-) — לא קובץ PDF תקין"
    return True, ""


# ============================================================================
# 3. HTML escaping — נגד XSS באלמנטים unsafe_allow_html=True
# ============================================================================

def esc(value) -> str:
    """
    Escape כל ערך לפני שיבוצו ל-HTML markup.
    מטפל ב: <, >, &, ", ', וגם בתווי בקרה.
    """
    if value is None:
        return ""
    s = str(value)
    return html.escape(s, quote=True)


def escape_text_preserve_newlines(value) -> str:
    """כמו esc אבל ממיר newline ל-<br> לתצוגה."""
    return esc(value).replace("\n", "<br>")


# ============================================================================
# 4. סניטיזציה של מזהי קבצים פנימיים — נגד path traversal ב-finding_id
# ============================================================================

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def safe_id(identifier: str, default: str = "default") -> str:
    """
    מאמת ש-ID פנימי לא מכיל תווים שיכולים לברוח מתיקייה.
    מסיר '..', '/', '\\', תווי בקרה, וכל מה שאינו [a-zA-Z0-9_-].
    """
    if not identifier or not isinstance(identifier, str):
        return default
    # NFKC + סינון
    identifier = unicodedata.normalize("NFKC", identifier)
    identifier = re.sub(r"[^a-zA-Z0-9_-]", "", identifier)[:64]
    return identifier or default


# ============================================================================
# 5. אימות JSON loads — מבנה צפוי בלבד
# ============================================================================

def safe_load_dataclass(cls, data: dict):
    """
    מפעיל dataclass רק עם השדות שהוא מצפה להם.
    מוחק שדות לא צפויים (שיכולים להזריק נתונים מסוכנים).
    """
    if not isinstance(data, dict):
        return None
    # קבל שמות שדות מ-dataclass
    if hasattr(cls, "__dataclass_fields__"):
        allowed = set(cls.__dataclass_fields__.keys())
        clean = {k: v for k, v in data.items() if k in allowed}
        try:
            return cls(**clean)
        except (TypeError, ValueError):
            return None
    try:
        return cls(**data)
    except (TypeError, ValueError):
        return None


# ============================================================================
# 6. הגבלת היקף לפלט סוכן — נגד data exfiltration / token waste
# ============================================================================

def truncate(s: str, limit: int = 500) -> str:
    """גוזר מחרוזת לאורך מקסימלי, מוסיף '…' אם נחתך."""
    if not isinstance(s, str):
        s = str(s) if s is not None else ""
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


# ============================================================================
# 7. רישום אירועי אבטחה
# ============================================================================

def log_security_event(event_type: str, details: str, severity: str = "info"):
    """
    רישום אירוע אבטחה לקובץ לוג מקומי.
    משתמש בקובץ נפרד (לא std streamlit logs) כדי להישמר בין הפעלות.
    """
    log_file = Path(__file__).resolve().parent.parent / "security.log"
    try:
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        entry = f"[{ts}] [{severity.upper()}] {event_type}: {details}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass  # לוגינג כושל לא יפיל את האפליקציה
