"""
מנוע השוואה: מבנה רחב לפי כללי הבנקאות (נבו) + דו"ח חריגות.
"""

from __future__ import annotations
import re
import statistics
import pandas as pd

from .schema import CANONICAL_FEES, FEE_BY_KEY, PARTS_ORDER
from .normalizer import NormalizedFee
from .bank_profiles import PROFILES_BY_ID


META_COLS = {"קוד רשמי", "חלק", "שם העמלה (כללי בנק ישראל)",
             "בפיקוח", "הערה רגולטורית", "💰 הזול ביותר"}


def _format_cell(f: NormalizedFee | None) -> str:
    if f is None:
        return "—"
    parts: list[str] = []
    if f.price_value is not None:
        suffix = "%" if f.price_unit == "percent" else " ₪"
        parts.append(f"{f.price_value:g}{suffix}")
    elif f.price_text:
        parts.append(f.price_text[:40])
    else:
        parts.append("?")
    if f.notes:
        parts.append(f.notes)
    if f.deviation:
        parts.append(f.deviation)
    return "\n".join(parts)


def build_comparison(
    by_bank: dict[str, dict[str, NormalizedFee]],
    fee_keys: list[str] | None = None,
    only_regulated: bool = False,
    only_with_data: bool = False,
    parts: list[str] | None = None,
) -> pd.DataFrame:
    if fee_keys is None:
        fee_keys = [f.key for f in CANONICAL_FEES]
    if only_regulated:
        fee_keys = [k for k in fee_keys if FEE_BY_KEY[k].regulated]
    if parts is not None:
        fee_keys = [k for k in fee_keys if FEE_BY_KEY[k].part in parts]

    rows = []
    for k in fee_keys:
        fee = FEE_BY_KEY[k]
        row: dict[str, str] = {
            "חלק": fee.part,
            "קוד רשמי": fee.code,
            "שם העמלה (כללי בנק ישראל)": fee.he_name,
            "בפיקוח": "✓" if fee.regulated else "",
            "הערה רגולטורית": fee.notes,
        }
        for bank_id, fees in by_bank.items():
            display = (PROFILES_BY_ID[bank_id].display_name
                       if bank_id in PROFILES_BY_ID else bank_id)
            row[display] = _format_cell(fees.get(k))
        rows.append(row)

    df = pd.DataFrame(rows)

    if only_with_data:
        bank_cols = [c for c in df.columns if c not in META_COLS]
        mask = df[bank_cols].apply(lambda r: any(v != "—" for v in r), axis=1)
        df = df[mask].reset_index(drop=True)

    return df


def cheapest_per_fee(df: pd.DataFrame, bank_cols: list[str]) -> pd.DataFrame:
    def _num(s):
        if s == "—":
            return None
        m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
        return float(m.group()) if m else None

    winners = []
    for _, row in df.iterrows():
        best_bank, best_val = None, None
        for c in bank_cols:
            v = _num(row[c])
            if v is None:
                continue
            if best_val is None or v < best_val:
                best_val, best_bank = v, c
        winners.append(best_bank or "—")
    df = df.copy()
    df["💰 הזול ביותר"] = winners
    return df


def get_bank_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META_COLS]


# ============================================================================
# דו"ח חריגות — דרישה ייעודית של המשתמש
# ============================================================================

def _extract_number(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(m.group()) if m else None


def build_deviation_report(
    by_bank: dict[str, dict[str, NormalizedFee]],
    *,
    outlier_factor: float = 2.0,
    rename_score_threshold: int = 95,
) -> pd.DataFrame:
    """
    מחזיר טבלת חריגות עם הטיפוסים:
    - 🏷️ שם שונה: הבנק משתמש בכינוי שלא תואם לשם הרשמי (score < 95).
    - ❌ עמלה חסרה: בנק לא מציע עמלה שכן קיימת אצל מתחרים.
    - 💸 חריגה בסכום: ערך > outlier_factor × חציון הבנקים, או < 1/outlier_factor.
    - ⚠ עמלה ייחודית: בנק אחד מציע עמלה שלא קיימת אצל אף בנק אחר.
    """
    rows = []

    for fee_def in CANONICAL_FEES:
        k = fee_def.key
        values_by_bank: dict[str, float] = {}
        offered_by: list[str] = []

        for bank_id, fees in by_bank.items():
            display = (PROFILES_BY_ID[bank_id].display_name
                       if bank_id in PROFILES_BY_ID else bank_id)
            f = fees.get(k)
            if f is None:
                continue
            offered_by.append(display)

            # --- 1) שם שונה ---
            if f.deviation:
                severity = "גבוהה" if f.match_score < 80 else "נמוכה"
                rows.append({
                    "סוג חריגה": "🏷️ שם שונה",
                    "חלק": fee_def.part,
                    "קוד רשמי": fee_def.code,
                    "שם רשמי": fee_def.he_name,
                    "בנק": display,
                    "פרטים": f.deviation,
                    "ערך אצל הבנק": f.price_text[:60],
                    "חומרה": severity,
                })

            # סכום מספרי לבדיקת outlier
            if f.price_value is not None:
                values_by_bank[display] = f.price_value

        # --- 2) עמלה חסרה / ייחודית ---
        if len(by_bank) > 1:
            present = set(offered_by)
            missing = [
                (PROFILES_BY_ID[bid].display_name if bid in PROFILES_BY_ID else bid)
                for bid in by_bank.keys()
                if (PROFILES_BY_ID.get(bid, bid)
                    and (PROFILES_BY_ID[bid].display_name
                         if bid in PROFILES_BY_ID else bid) not in present)
            ]
            if present and missing and len(present) >= 2:
                rows.append({
                    "סוג חריגה": "❌ עמלה חסרה",
                    "חלק": fee_def.part,
                    "קוד רשמי": fee_def.code,
                    "שם רשמי": fee_def.he_name,
                    "בנק": " · ".join(missing),
                    "פרטים": f"לא נמצאה עמלה זו ({len(missing)} בנקים), בעוד {len(present)} בנקים גובים אותה.",
                    "ערך אצל הבנק": "—",
                    "חומרה": "נמוכה",
                })
            elif len(present) == 1 and len(by_bank) >= 3:
                rows.append({
                    "סוג חריגה": "⚠ עמלה ייחודית",
                    "חלק": fee_def.part,
                    "קוד רשמי": fee_def.code,
                    "שם רשמי": fee_def.he_name,
                    "בנק": offered_by[0],
                    "פרטים": "רק בנק זה מציע את העמלה — בדוק אם זה שירות ייחודי או שגיאת חילוץ.",
                    "ערך אצל הבנק": str(values_by_bank.get(offered_by[0], "?")),
                    "חומרה": "נמוכה",
                })

        # --- 3) חריגה בסכום ---
        if len(values_by_bank) >= 3:
            vals = list(values_by_bank.values())
            median = statistics.median(vals)
            if median > 0:
                for bank_name, v in values_by_bank.items():
                    if v == 0:
                        continue
                    ratio = v / median
                    if ratio >= outlier_factor or ratio <= 1 / outlier_factor:
                        severity = "גבוהה" if (ratio >= 3 or ratio <= 0.33) else "בינונית"
                        direction = "יקר משמעותית" if ratio > 1 else "זול משמעותית"
                        rows.append({
                            "סוג חריגה": "💸 חריגה בסכום",
                            "חלק": fee_def.part,
                            "קוד רשמי": fee_def.code,
                            "שם רשמי": fee_def.he_name,
                            "בנק": bank_name,
                            "פרטים": f"{direction}: ₪{v:g} לעומת חציון ₪{median:g} ({ratio:.1f}×)",
                            "ערך אצל הבנק": f"{v:g} ₪",
                            "חומרה": severity,
                        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # מיון: חומרה גבוהה לפני נמוכה
    severity_order = {"גבוהה": 0, "בינונית": 1, "נמוכה": 2}
    df["_sev"] = df["חומרה"].map(severity_order).fillna(99)
    df = df.sort_values(["_sev", "חלק", "קוד רשמי"]).drop(columns="_sev").reset_index(drop=True)
    return df
