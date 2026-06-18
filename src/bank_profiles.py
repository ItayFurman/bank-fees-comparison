"""
פרופילים פר-בנק: שם תצוגה + override-ים על מילות מפתח/דפי הסעיף.
הוספת בנק חדש = הוספת רשומה כאן + הנחת PDF בתיקיית pdfs/.
"""

from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class BankProfile:
    bank_id: str
    display_name: str
    filename_hints: list[str] = field(default_factory=list)
    extra_keywords: dict[str, list[str]] = field(default_factory=dict)
    brand_color: str = "#5f6368"     # צבע המותג של הבנק (CSS hex)
    text_color: str = "#ffffff"       # צבע טקסט קריא על רקע המותג

# צבעי מותג רשמיים (מבוסס על לוגואים ואתרי הבנקים)
PROFILES: list[BankProfile] = [
    # ⚠ "beinleumi" חייב להופיע לפני "leumi"
    BankProfile("beinleumi",  "הבנק הבינלאומי", ["בינלאומי", "beinleumi", "fibi"],
                brand_color="#003478", text_color="#ffffff"),   # כחול בינלאומי
    BankProfile("leumi",      "בנק לאומי",      ["לאומי", "leumi"],
                brand_color="#bf002b", text_color="#ffffff"),   # אדום לאומי
    BankProfile("hapoalim",   "בנק הפועלים",
                ["הפועלים", "poalim", "small_business", "single_small_business", "small_single"],
                brand_color="#e30613", text_color="#ffffff"),   # אדום הפועלים
    BankProfile("discount",   "בנק דיסקונט",
                ["דיסקונט", "discount", "tarif_small", "tarif_private"],
                brand_color="#00a651", text_color="#ffffff"),   # ירוק דיסקונט
    BankProfile("mizrahi",    "בנק מזרחי טפחות",
                ["מזרחי", "טפחות", "mizrahi", "smallbusiness"],
                brand_color="#f7941d", text_color="#ffffff"),   # כתום מזרחי
    BankProfile("mercantile", "בנק מרכנתיל",
                ["מרכנתיל", "mercantile", "taarifon_private_full"],
                brand_color="#006847", text_color="#ffffff"),   # ירוק כהה
    BankProfile("yahav",      "בנק יהב",        ["יהב", "yahav"],
                brand_color="#1a4378", text_color="#ffffff"),   # כחול כהה
    BankProfile("jerusalem",  "בנק ירושלים",
                ["ירושלים", "jerusalem", "1759"],  # 1759 = timestamp prefix
                brand_color="#8b4513", text_color="#ffffff"),   # חום ירושלים
    BankProfile("massad",     "בנק מסד",        ["מסד", "massad"],
                brand_color="#003a6c", text_color="#ffffff"),   # כחול מסד
    BankProfile("one_zero",   "וואן זירו",      ["וואן", "one zero", "one-zero", "onezero"],
                brand_color="#0a0a0a", text_color="#ffffff"),   # שחור וואן זירו
    BankProfile("max",        "מקס (Max)",      ["מקס", "max"],
                brand_color="#00bfb3", text_color="#ffffff"),   # טורקיז מקס
]

def detect_bank(filename: str) -> BankProfile | None:
    name = filename.lower()
    for p in PROFILES:
        for hint in p.filename_hints:
            if hint.lower() in name:
                return p
    return None

PROFILES_BY_ID = {p.bank_id: p for p in PROFILES}
