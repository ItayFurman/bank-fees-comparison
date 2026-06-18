"""
סוכן ניטור תאימות רגולטורית — גרסה משופרת.

מבוסס על:
  • כללי הבנקאות (שירות ללקוח) (עמלות), התשס"ח-2008 (159a / תוספת ראשונה).
  • מכתב המפקח על הבנקים, סימוכין 25LM5593, 10.12.2025 (202529.pdf).

7 קטגוריות סיכון + ציון סיכון פר-בנק + ציטוטים ממקור + תבניות מייל
ייחודיות לכל קטגוריה.
"""
from __future__ import annotations
import json
import re
import statistics
import uuid
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from .schema import CANONICAL_FEES, FEE_BY_KEY
from .normalizer import NormalizedFee
from .bank_profiles import PROFILES_BY_ID


# ============================================================================
# מאגר הידע: 7 קטגוריות סיכון
# ============================================================================

RISK_CATEGORIES = {
    "R1_NEW_SERVICE_NO_APPROVAL": {
        "title": "שירות חדש ללא אישור מפקח",
        "short": "שירות לא מוכר",
        "basis": "סעיף 9ט(ה) לחוק הבנקאות (שירות ללקוח) + חלק ראשון, סעיף 1 למכתב המפקח 25LM5593",
        "exposure": "תובענה ייצוגית + עיצום כספי",
        "weight": 8,
        "explanation":
            "תאגיד בנקאי אינו רשאי לגבות עמלה בעד שירות שאינו קיים בכללי "
            "העמלות (תעריפון מלא ליחיד/עסק קטן) ללא אישור מראש של המפקח "
            "ופרסום ברשומות. גם הוספת שירות שכבר קיים בתעריפון המלא נחשבת "
            "להעלאת תעריף (חלק ראשון, סעיף 3 למכתב).",
        "email_template": "R1",
    },
    "R2_PRICE_HIKE_NO_REPORT": {
        "title": "חשד להעלאת תעריף חורגת",
        "short": "תעריף חורג",
        "basis": "סעיפים 9יג-9טו לחוק + חלק ראשון, סעיף 2 למכתב",
        "exposure": "עיצום כספי על אי-דיווח/אי-אישור",
        "weight": 7,
        "explanation":
            "שירות בר-פיקוח דורש אישור מפקח להעלאת תעריף; שירות שאינו בר-"
            "פיקוח דורש דיווח 30 יום מראש. תעריף שחורג משמעותית מהשוק מצריך "
            "בחינה האם ההעלאה דווחה כראוי. הפיקוח הבהיר במכתב 10.12.2025 "
            "שחיווי 'נרשם דיווח' אינו אישור לעצם ההעלאה.",
        "email_template": "R2",
    },
    "R3_DUPLICATE_FEE_SAME_SERVICE": {
        "title": "כפילות עמלות לאותו שירות",
        "short": "כפילות פנימית",
        "basis": "סעיף 9ט(ד) לחוק",
        "exposure": "תובענה ייצוגית",
        "weight": 9,
        "explanation":
            "החוק אוסר במפורש גביית עמלות שונות בעד אותו שירות. אם בנק "
            "רשם שני פריטים שונים בתעריפון לאותה מהות (לדוגמה: גם 'פעולה "
            "על ידי פקיד' וגם 'פעולת פקיד בסניף' עם תעריפים שונים) — "
            "מתעורר חשד לעבירה.",
        "email_template": "R3",
    },
    "R4_PART9_SPECIAL_SERVICES": {
        "title": "שירות בחלק 9 ללא אישור (פסיקת סמוחה)",
        "short": "חלק 9 ללא אישור",
        "basis": "חלק שני, סעיף 2 למכתב + ת\"צ 37816-09-19 סמוחה נ' בנק הפועלים (12.12.2024)",
        "exposure": "תובענה ייצוגית — עמדת בנק ישראל בבית המשפט תומכת בלקוחות",
        "weight": 9,
        "explanation":
            "חלק 9 לתעריפון המלא — \"שירותים מיוחדים לפי פירוט שיקבע "
            "התאגיד\" — מחייב מ-12.12.2024 אישור מפקח ופרסום ברשומות, על "
            "אף הניסוח הגמיש בכללים. שינוי המדיניות פורסם בעמדת המאסדר "
            "באתר בנק ישראל. תאגיד שהוסיף שירות לחלק 9 ללא אישור — חשוף "
            "לתובענה ייצוגית.",
        "email_template": "R4",
    },
    "R5_MODIFIED_NOTES_FIELD": {
        "title": "שינוי שדה ההערות בתעריפון המלא",
        "short": "הערות לא רשמיות",
        "basis": "חלק שני, סעיף 3 למכתב + ת\"צ 51664-12-20 + 51676-12-20 סמוחה וגוטמן (25.11.2024)",
        "exposure": "תובענה ייצוגית — נ' הפועלים, לאומי, דיסקונט, מזרחי",
        "weight": 7,
        "explanation":
            "שדה ההערות בתעריפון המלא נקבע במדויק בכללי העמלות. תאגיד "
            "בנקאי אינו רשאי לערוך בו שינויים אלא באמצעות תיקון הכללים — "
            "גם אם שינויים נכללו בהסדרי פשרה בתובענות קודמות (מכתב המפקח "
            "מבהיר זאת במפורש).",
        "email_template": "R5",
    },
    "R6_THIRD_PARTY_EXPENSES_DISCLOSURE": {
        "title": "חוסר גילוי הוצאות צד שלישי (חלק 11)",
        "short": "הוצ׳ צד ג׳",
        "basis": "חלק שני, סעיף 4 למכתב + מכתב הפיקוח 16.2.2022",
        "exposure": "תובענה ייצוגית בגין הטעיה / חוסר גילוי",
        "weight": 6,
        "explanation":
            "תאגיד בנקאי שגובה הוצאות צד שלישי חייב לציין אותן הן בחלק 11 "
            "והן לצד השירות הרלוונטי. אם ההוצאה אינה אחידה — חייב לשקף את "
            "העלות הממשית הצפויה (לרבות מחיר מקסימום או הפניה לתעריפון "
            "רשמי כמו דואר ישראל / תקנות נוטריונים).",
        "email_template": "R6",
    },
    "R7_DATA_QUALITY": {
        "title": "איכות נתונים — תעריפון לא קריא",
        "short": "PDF לא קריא",
        "basis": "—",
        "exposure": "אינו ליקוי משפטי — דורש קובץ חלופי",
        "weight": 1,
        "explanation":
            "ה-PDF של הבנק לא נחלץ כראוי (פונט CID לא-Unicode, או פורמט "
            "שאינו טבלאי). יש להשיג גרסה חלופית של התעריפון, או לבחון "
            "ידנית, כדי לבצע ניתוח תאימות מלא. זהו רישום טכני, לא ליקוי.",
        "email_template": "R7",
    },
}


# ============================================================================
# מודל ממצא משופר
# ============================================================================

@dataclass
class ComplianceFinding:
    finding_id: str
    risk_category: str
    severity: str                # "קריטית" / "גבוהה" / "בינונית" / "נמוכה"
    bank: str
    fee_code: str = ""
    fee_name: str = ""
    part: str = ""               # מאיזה חלק בתעריפון
    title: str = ""
    description: str = ""
    bank_quote: str = ""         # ציטוט ישיר מהבנק
    regulation_quote: str = ""   # ציטוט ישיר מהכללים/מכתב
    suggested_action: str = ""   # פעולה מומלצת
    evidence: dict = field(default_factory=dict)
    page_in_pdf: int = -1
    user_verdict: str = ""       # "אושר" / "נדחה" / ""
    user_notes: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def stable_key(self) -> str:
        """מפתח יציב להתאמה בין ריצות (לשמירת verdict של הבוחן)."""
        return f"{self.bank}::{self.risk_category}::{self.fee_code}::{self.title[:50]}"


# ============================================================================
# סורקים פר-קטגוריה
# ============================================================================

def _bank_display(bank_id: str) -> str:
    return (PROFILES_BY_ID[bank_id].display_name
            if bank_id in PROFILES_BY_ID else bank_id)


def build_cross_bank_comparison(
    by_bank: dict[str, dict[str, NormalizedFee]],
    fee_key: str,
) -> dict:
    """
    מחזיר השוואה רוחבית מלאה בין כל הבנקים על עמלה אחת.
    מבנה התוצאה:
      {
        'fee_key': str, 'fee_name': str, 'fee_code': str, 'part': str,
        'unit': 'ILS'/'percent',
        'banks': [
          {'bank': str, 'price': float, 'price_text': str, 'notes': str,
           'source_label': str, 'page': int}, ...
        ],
        'stats': {'min': float, 'max': float, 'median': float,
                  'mean': float, 'count': int, 'missing': [str]}
      }
    """
    fee_def = FEE_BY_KEY.get(fee_key)
    if not fee_def:
        return {}

    banks_data: list[dict] = []
    missing: list[str] = []
    for bank_id, fees in by_bank.items():
        bn = _bank_display(bank_id)
        f = fees.get(fee_key)
        if f is None:
            missing.append(bn)
            continue
        banks_data.append({
            "bank": bn,
            "bank_id": bank_id,
            "price": f.price_value,
            "price_text": f.price_text,
            "notes": f.notes,
            "source_label": f.source_label,
            "page": f.page,
            "unit": f.price_unit,
        })

    # מיון מהזול לייקר
    with_price = [b for b in banks_data if b["price"] is not None]
    with_price.sort(key=lambda b: b["price"])
    without_price = [b for b in banks_data if b["price"] is None]

    prices = [b["price"] for b in with_price if b["price"] is not None]
    stats: dict = {"count": len(prices), "missing": missing}
    if prices:
        stats.update({
            "min": min(prices),
            "max": max(prices),
            "median": statistics.median(prices),
            "mean": statistics.mean(prices),
            "cheapest": with_price[0]["bank"],
            "most_expensive": with_price[-1]["bank"],
        })

    return {
        "fee_key": fee_key,
        "fee_name": fee_def.he_name,
        "fee_code": fee_def.code,
        "part": fee_def.part,
        "unit": fee_def.unit,
        "regulated": fee_def.regulated,
        "banks": with_price + without_price,
        "stats": stats,
    }


def get_comparison_for_finding(
    finding: ComplianceFinding,
    by_bank: dict[str, dict[str, NormalizedFee]],
) -> dict | None:
    """החזרת השוואה רוחבית רק אם לממצא יש fee_key מזוהה."""
    # מצא את ה-fee_key לפי fee_code
    if not finding.fee_code:
        return None
    for fee in CANONICAL_FEES:
        if fee.code == finding.fee_code and fee.he_name == finding.fee_name:
            return build_cross_bank_comparison(by_bank, fee.key)
    return None


def _bank_has_data(by_bank, bank_id, min_fees: int = 3) -> bool:
    return len(by_bank.get(bank_id, {})) >= min_fees


def _scan_R1_R4_unmatched(by_bank, raw_rows_by_bank) -> list[ComplianceFinding]:
    """
    R1+R4: שורות שלא הותאמו לעמלה קנונית — חשד לשירות חדש (R1) או חלק 9 (R4).
    """
    findings = []
    for bank_id, rows in raw_rows_by_bank.items():
        bank_name = _bank_display(bank_id)
        unmatched = rows.get("unmatched_high_signal", [])
        for ru in unmatched[:5]:
            label = ru.get("label", "")
            value = ru.get("value", "")

            # זיהוי חלק 9 לפי מילים מאפיינות
            is_part9 = any(kw in label for kw in [
                "כספת", "כספות", "ירושה", "עיזבון", "ייעוץ פנסיוני",
                "שמירת דואר", "המחאת זכות", "שטרות"])

            category = "R4_PART9_SPECIAL_SERVICES" if is_part9 else "R1_NEW_SERVICE_NO_APPROVAL"
            severity = "קריטית" if is_part9 else "גבוהה"
            rc = RISK_CATEGORIES[category]

            findings.append(ComplianceFinding(
                finding_id=str(uuid.uuid4())[:8],
                risk_category=category,
                severity=severity,
                bank=bank_name,
                fee_code="",
                fee_name=label[:60],
                title=f"שירות לא מוכר: {label[:55]}",
                description=(
                    f"בתעריפון הבנק נמצא פריט שלא הותאם לעמלה רשמית: "
                    f"\"{label[:140]}\" במחיר \"{value[:80]}\". "
                    + ("מאפיין חלק 9 — דורש אישור מפקח ופרסום ברשומות "
                       "מ-12.12.2024 (ת\"צ סמוחה)." if is_part9 else
                       "חשד לשירות חדש ללא אישור מפקח לפי סעיף 9ט(ה).")
                ),
                bank_quote=label[:200],
                regulation_quote=rc["explanation"][:300],
                suggested_action=(
                    f"1. אמת בעמוד {ru.get('page', '?')} ב-PDF.\n"
                    f"2. בדוק האם השירות מופיע בכללי העמלות "
                    f"(תוספת ראשונה) או דורש אישור מפקח לפי סעיף 9ט(ה).\n"
                    f"3. " + ("הואיל וזה חלק 9, ודא שאושר ופורסם ברשומות אחרי 12.12.2024."
                              if is_part9 else
                              "אם השירות חדש — הבנק חשוף לתובענה ייצוגית.")
                ),
                evidence={"raw_label": label, "raw_value": value,
                          "page": ru.get("page", -1)},
                page_in_pdf=ru.get("page", -1),
            ))
    return findings


def _scan_R2_price_outliers(by_bank, *, factor: float = 3.0) -> list[ComplianceFinding]:
    """R2: בנק שגובה תעריף חורג ביותר מ-factor × חציון."""
    findings = []
    active = {bid: f for bid, f in by_bank.items() if _bank_has_data(by_bank, bid)}
    for fee in CANONICAL_FEES:
        values: dict[str, tuple[float, NormalizedFee]] = {}
        for bank_id, fees in active.items():
            f = fees.get(fee.key)
            if f and f.price_value is not None and f.price_value > 0:
                values[_bank_display(bank_id)] = (f.price_value, f)
        if len(values) < 3:
            continue
        nums = [v[0] for v in values.values()]
        median = statistics.median(nums)
        if median <= 0:
            continue
        for bank_name, (v, nf) in values.items():
            ratio = v / median
            if ratio >= factor:
                severity = "קריטית" if ratio >= 5 else "גבוהה"
                rc = RISK_CATEGORIES["R2_PRICE_HIKE_NO_REPORT"]
                findings.append(ComplianceFinding(
                    finding_id=str(uuid.uuid4())[:8],
                    risk_category="R2_PRICE_HIKE_NO_REPORT",
                    severity=severity,
                    bank=bank_name,
                    fee_code=fee.code,
                    fee_name=fee.he_name,
                    part=fee.part,
                    title=f"{bank_name}: ₪{v:g} מול חציון ₪{median:g} (×{ratio:.1f})",
                    description=(
                        f"בעמלת '{fee.he_name}' (קוד רשמי {fee.code}, "
                        f"{fee.part}), הבנק גובה ₪{v:g} בעוד החציון בשוק "
                        f"עומד על ₪{median:g}. פער של פי {ratio:.1f} מעורר "
                        f"חשד להעלאת תעריף שלא דווחה/אושרה כראוי."
                    ),
                    bank_quote=nf.price_text[:200] if nf.price_text else "",
                    regulation_quote=rc["explanation"][:300],
                    suggested_action=(
                        f"1. בדוק במערכת הפיקוח האם הבנק דיווח על השינוי "
                        f"(9טו לחוק) או קיבל אישור (9יג-9יד).\n"
                        f"2. השווה לתעריף ההיסטורי של הבנק (ארכיון "
                        f"אתר הבנק).\n"
                        f"3. אם זה שירות בפיקוח — דרוש אישור מפקח. "
                        f"חיווי 'נרשם דיווח' לא אישור."
                    ),
                    evidence={"bank_price": v, "market_median": median,
                              "ratio": ratio, "all_banks": {
                                  b: vv[0] for b, vv in values.items()}},
                    page_in_pdf=nf.page,
                ))
    return findings


def _scan_R3_internal_duplicates(by_bank, raw_rows_by_bank) -> list[ComplianceFinding]:
    """
    R3: בנק שיש לו עמלות שונות לאותו שירות (כפילות).
    מזהה אם 2+ שורות גולמיות באותו בנק התאימו לאותו fee_key.
    הכי טוב לזהות מתוך הנרמול הרציני - נסמן בנק שיש לו פריטים עם
    שני תעריפים שונים לאותה עמלה קנונית.
    """
    findings = []
    # אנחנו צריכים לחזור על raw_rows - אבל יש לנו רק unmatched.
    # במקום זה, נאתר בנקים שלהם יותר משורה אחת המתאימה לאותו fee_key
    # דרך הסתכלות בכל הפלט שלהם
    # זה דורש להריץ שוב התאמה - בהקשר הזה אנחנו מקבלים רק normalized.
    # אז נסמן: אם יש unmatched שמכיל את אותה מילת מפתח של עמלה קיימת
    for bank_id, rows in raw_rows_by_bank.items():
        bank_name = _bank_display(bank_id)
        existing_fees = by_bank.get(bank_id, {})
        unmatched = rows.get("unmatched_high_signal", [])

        for ru in unmatched:
            label = ru.get("label", "")
            value = ru.get("value", "")
            # אם יש מספר בערך והתווית מזכירה עמלה רשמית קיימת — חשד לכפילות
            for fee_key, nf in existing_fees.items():
                fee_def = FEE_BY_KEY.get(fee_key)
                if not fee_def:
                    continue
                # מצא חפיפה משמעותית בין תוויות
                official_words = set(fee_def.he_name.split())
                label_words = set(label.split())
                overlap = len(official_words & label_words)
                if overlap >= 2:
                    # יש שתי מילים זהות בין השם הרשמי לבין השורה הלא-מותאמת
                    # זה חשד חזק לכפילות
                    rc = RISK_CATEGORIES["R3_DUPLICATE_FEE_SAME_SERVICE"]
                    findings.append(ComplianceFinding(
                        finding_id=str(uuid.uuid4())[:8],
                        risk_category="R3_DUPLICATE_FEE_SAME_SERVICE",
                        severity="גבוהה",
                        bank=bank_name,
                        fee_code=fee_def.code,
                        fee_name=fee_def.he_name,
                        part=fee_def.part,
                        title=f"כפילות פוטנציאלית בעמלת {fee_def.he_name}",
                        description=(
                            f"לבנק יש פריט מזוהה: '{fee_def.he_name}' "
                            f"(תעריף: {nf.price_text[:50]}), וגם שורה לא-"
                            f"מותאמת נוספת עם מילים זהות: \"{label[:80]}\" "
                            f"(תעריף: {value[:50]}). חשד לעבירה על סעיף "
                            f"9ט(ד) — גביית עמלות שונות לאותו שירות."
                        ),
                        bank_quote=f"פריט 1: {nf.price_text[:80]}\n"
                                   f"פריט 2: {label[:80]} → {value[:50]}",
                        regulation_quote=rc["explanation"][:300],
                        suggested_action=(
                            "1. אמת מול ה-PDF המקורי שאכן מדובר בשני פריטים נפרדים.\n"
                            "2. אם כן — בדוק האם זהות מהותית בין השירותים.\n"
                            "3. אם זהות — הבנק חשוף לתובענה ייצוגית מכוח 9ט(ד)."
                        ),
                        evidence={"item1_text": nf.price_text,
                                  "item2_label": label, "item2_value": value,
                                  "overlap_words": list(official_words & label_words)},
                        page_in_pdf=ru.get("page", -1),
                    ))
                    break  # אחד לכל unmatched מספיק
    return findings


def _scan_R5_notes_modification(by_bank) -> list[ComplianceFinding]:
    """R5: עמלות עם הערות חריגות שמשנות את שדה ההערות."""
    findings = []
    suspicious_keywords = [
        "אלא", "למעט", "בכפוף ל", "ככל ש", "לא יחול",
        "תיגבה רק", "בתנאי ש", "פרט ל"]
    for bank_id, fees in by_bank.items():
        bank_name = _bank_display(bank_id)
        for fee_key, f in fees.items():
            if len(f.price_text) < 80:
                continue
            matches = [kw for kw in suspicious_keywords if kw in f.price_text]
            if not matches:
                continue
            fee_def = FEE_BY_KEY.get(fee_key)
            if not fee_def:
                continue
            rc = RISK_CATEGORIES["R5_MODIFIED_NOTES_FIELD"]
            findings.append(ComplianceFinding(
                finding_id=str(uuid.uuid4())[:8],
                risk_category="R5_MODIFIED_NOTES_FIELD",
                severity="בינונית",
                bank=bank_name,
                fee_code=fee_def.code,
                fee_name=fee_def.he_name,
                part=fee_def.part,
                title=f"הערה חריגה ב-{fee_def.he_name}",
                description=(
                    f"בעמלת '{fee_def.he_name}' (קוד {fee_def.code}) "
                    f"זוהתה הערה ארוכה הכוללת ביטויים מגבילים: "
                    f"{', '.join(repr(m) for m in matches[:3])}. "
                    f"לפי ת\"צ סמוחה וגוטמן (25.11.2024), שדה ההערות "
                    f"נקבע מדויק בכללי העמלות ואסור לערוך בו שינויים."
                ),
                bank_quote=f.price_text[:250],
                regulation_quote=rc["explanation"][:300],
                suggested_action=(
                    "1. השווה את ההערה בבנק להערה הרשמית בכללי העמלות.\n"
                    "2. אם ההערה מעבר למה שמותר — הבנק חייב להגיש בקשה "
                    "לתיקון הכללים, לא לשנות בעצמו.\n"
                    "3. הסבר נוסף ללקוח יכול להימסר מחוץ לתעריפון."
                ),
                evidence={"full_text": f.price_text,
                          "suspicious_words": matches},
                page_in_pdf=f.page,
            ))
    return findings


def _scan_R6_third_party(by_bank) -> list[ComplianceFinding]:
    """R6: עמלות שרוב הבנקים גובים אך הבנק לא — חשד לאי-גילוי."""
    findings = []
    active = {bid: f for bid, f in by_bank.items() if _bank_has_data(by_bank, bid)}
    if len(active) < 4:
        return findings
    for fee in CANONICAL_FEES:
        # נטפל ב-R6 רק עבור חלק 11 (הוצ' צד ג') ועמלות שנגבות בפועל
        if fee.part != "חלק 11 - הוצאות צד שלישי":
            continue
        present, missing = [], []
        for bank_id, fees in active.items():
            bn = _bank_display(bank_id)
            if fee.key in fees:
                present.append(bn)
            else:
                missing.append(bn)
        if len(present) >= 3 and len(missing) >= 1:
            for bank_name in missing:
                rc = RISK_CATEGORIES["R6_THIRD_PARTY_EXPENSES_DISCLOSURE"]
                findings.append(ComplianceFinding(
                    finding_id=str(uuid.uuid4())[:8],
                    risk_category="R6_THIRD_PARTY_EXPENSES_DISCLOSURE",
                    severity="נמוכה",
                    bank=bank_name,
                    fee_code=fee.code,
                    fee_name=fee.he_name,
                    part=fee.part,
                    title=f"חסר: {fee.he_name} ({len(present)} בנקים אחרים מציגים)",
                    description=(
                        f"הוצאת צד שלישי '{fee.he_name}' מופיעה אצל "
                        f"{len(present)} בנקים: {', '.join(present[:3])}. "
                        f"אם הבנק מספק את השירות, עליו לציין את העלות "
                        f"בתעריפון — הן בחלק 11 והן לצד השירות הרלוונטי "
                        f"(חלק שני, סעיף 4.5 למכתב המפקח)."
                    ),
                    bank_quote="(אין רישום בתעריפון)",
                    regulation_quote=rc["explanation"][:300],
                    suggested_action=(
                        f"1. בדוק האם הבנק מספק את השירות בכלל.\n"
                        f"2. אם כן — מדוע לא רשום בתעריפון? "
                        f"חוסר גילוי = תובענה ייצוגית.\n"
                        f"3. השווה לבנקים הציגו: "
                        f"{', '.join(present[:3])}."
                    ),
                    evidence={"present_at": present,
                              "missing_at": [bank_name]},
                ))
    return findings


def _scan_R7_data_quality(by_bank) -> list[ComplianceFinding]:
    """R7: בנקים בלי נתונים מספיקים — לא ליקוי, אלא בעיית קלט."""
    findings = []
    for bank_id, fees in by_bank.items():
        if len(fees) >= 5:
            continue
        bank_name = _bank_display(bank_id)
        findings.append(ComplianceFinding(
            finding_id=str(uuid.uuid4())[:8],
            risk_category="R7_DATA_QUALITY",
            severity="נמוכה",
            bank=bank_name,
            title=f"חילוץ מוגבל: {bank_name} ({len(fees)} עמלות בלבד)",
            description=(
                f"מ-PDF התעריפון של {bank_name} חולצו {len(fees)} עמלות "
                f"בלבד. ייתכן בגלל פונט CID לא-Unicode, מבנה לא-טבלאי, "
                f"או PDF מבוסס תמונות. אין לבצע ניתוח תאימות על הבנק "
                f"הזה ללא קובץ חלופי."
            ),
            suggested_action=(
                "1. השג את התעריפון בפורמט Excel/CSV מאתר הבנק.\n"
                "2. או בקש מהבנק את הקובץ ישירות.\n"
                "3. או הפעל OCR (Tesseract) על ה-PDF."
            ),
            evidence={"matched_count": len(fees)},
        ))
    return findings


# ============================================================================
# סריקה כוללת + ציון סיכון פר-בנק
# ============================================================================

def scan_compliance(
    by_bank: dict[str, dict[str, NormalizedFee]],
    raw_rows_by_bank: dict[str, dict] | None = None,
    *,
    price_outlier_factor: float = 3.0,
) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    findings.extend(_scan_R2_price_outliers(by_bank, factor=price_outlier_factor))
    findings.extend(_scan_R5_notes_modification(by_bank))
    findings.extend(_scan_R6_third_party(by_bank))
    findings.extend(_scan_R7_data_quality(by_bank))
    if raw_rows_by_bank:
        findings.extend(_scan_R1_R4_unmatched(by_bank, raw_rows_by_bank))
        findings.extend(_scan_R3_internal_duplicates(by_bank, raw_rows_by_bank))

    sev_order = {"קריטית": 0, "גבוהה": 1, "בינונית": 2, "נמוכה": 3}
    findings.sort(key=lambda f: (sev_order.get(f.severity, 9),
                                  f.risk_category, f.bank))
    return findings


def bank_risk_scores(findings: list[ComplianceFinding]) -> dict[str, dict]:
    """
    מחשב ציון סיכון לכל בנק:
      score = sum(severity_weight * category_weight) לכל ממצא לא-נדחה.
    מחזיר {bank: {score, level, by_category, findings_count}}
    """
    sev_w = {"קריטית": 4, "גבוהה": 3, "בינונית": 2, "נמוכה": 1}
    scores: dict[str, dict] = defaultdict(
        lambda: {"score": 0, "by_category": Counter(),
                 "findings_count": 0, "verdicts": Counter()})

    for f in findings:
        # ממצא R7 לא משתתף בציון
        if f.risk_category == "R7_DATA_QUALITY":
            continue
        # נדחו ע"י הבוחן — לא משתתף
        if f.user_verdict == "נדחה":
            continue
        cat_w = RISK_CATEGORIES.get(f.risk_category, {}).get("weight", 5)
        sev = sev_w.get(f.severity, 1)
        scores[f.bank]["score"] += cat_w * sev
        scores[f.bank]["by_category"][f.risk_category] += 1
        scores[f.bank]["findings_count"] += 1
        scores[f.bank]["verdicts"][f.user_verdict or "טרם"] += 1

    # קבע רמה: גבוה (>80), בינוני (40-80), נמוך (<40)
    for bank, info in scores.items():
        s = info["score"]
        info["level"] = ("גבוה מאוד" if s >= 120 else
                         "גבוה" if s >= 80 else
                         "בינוני" if s >= 40 else "נמוך")
    return dict(scores)


def top_findings(findings: list[ComplianceFinding], n: int = 10) -> list[ComplianceFinding]:
    """N הממצאים המסוכנים ביותר (לא נדחו)."""
    sev_w = {"קריטית": 4, "גבוהה": 3, "בינונית": 2, "נמוכה": 1}
    def _score(f):
        cat_w = RISK_CATEGORIES.get(f.risk_category, {}).get("weight", 5)
        return -(cat_w * sev_w.get(f.severity, 1))  # שלילי לסידור מהגבוה לנמוך
    active = [f for f in findings
              if f.user_verdict != "נדחה"
              and f.risk_category != "R7_DATA_QUALITY"]
    active.sort(key=_score)
    return active[:n]


# ============================================================================
# שמירה וטעינה
# ============================================================================

MEMORY_DIR = Path(__file__).resolve().parent.parent / "agent_memory"


def save_findings(findings: list[ComplianceFinding]) -> Path:
    MEMORY_DIR.mkdir(exist_ok=True)
    f = MEMORY_DIR / "findings.json"
    f.write_text(
        json.dumps([x.to_dict() for x in findings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return f


def load_findings() -> list[ComplianceFinding]:
    f = MEMORY_DIR / "findings.json"
    if not f.exists():
        return []
    raw = json.loads(f.read_text(encoding="utf-8"))
    return [ComplianceFinding(**x) for x in raw]


def update_verdict(finding_id: str, verdict: str, notes: str = "") -> bool:
    findings = load_findings()
    for f in findings:
        if f.finding_id == finding_id:
            f.user_verdict = verdict
            f.user_notes = notes
            save_findings(findings)
            return True
    return False


def bulk_update_verdict(category: str | None, bank: str | None,
                       severity: str | None, verdict: str) -> int:
    """אישור/דחייה בכמות — מחזיר כמה ממצאים עודכנו."""
    findings = load_findings()
    n = 0
    for f in findings:
        if category and f.risk_category != category:
            continue
        if bank and f.bank != bank:
            continue
        if severity and f.severity != severity:
            continue
        f.user_verdict = verdict
        n += 1
    if n:
        save_findings(findings)
    return n


# ============================================================================
# מיזוג ממצאים חדשים עם verdict ישנים
# ============================================================================

def merge_with_history(new_findings: list[ComplianceFinding]) -> list[ComplianceFinding]:
    """שומר verdict של הבוחן מהריצה הקודמת על בסיס stable_key."""
    existing = load_findings()
    history = {f.stable_key: (f.user_verdict, f.user_notes, f.finding_id)
               for f in existing if f.user_verdict}
    for f in new_findings:
        prev = history.get(f.stable_key)
        if prev:
            f.user_verdict = prev[0]
            f.user_notes = prev[1]
            f.finding_id = prev[2]  # שומר על אותו ID לקישור שיחות
    return new_findings
