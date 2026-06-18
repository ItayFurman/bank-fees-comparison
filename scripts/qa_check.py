"""
כלי QA - בקרה אוטומטית של איכות החילוץ.
מסמן ערכים חשודים:
  - אחוז גבוה מ-50 בעמלות שאמורות להיות ₪
  - ערך מספרי קיצוני (>10,000 ₪) בעמלות תפעוליות
  - הערות בלי מספר
  - score נמוך (<85)
  - ערכים זהים בין בנקים שונים (חשד להעתקה)

הרצה:  python qa_check.py [--export qa_report.csv]
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.schema import FEE_BY_KEY
from src.bank_profiles import PROFILES_BY_ID


SUSPICIOUS = []

def add(severity, bank, fee_key, reason, value):
    SUSPICIOUS.append({
        "חומרה": severity, "בנק": bank, "קוד": FEE_BY_KEY.get(fee_key).code if fee_key in FEE_BY_KEY else "?",
        "עמלה": FEE_BY_KEY.get(fee_key).he_name if fee_key in FEE_BY_KEY else fee_key,
        "סיבה": reason, "ערך נחלץ": str(value)[:80]
    })

def main():
    import os
    os.chdir(ROOT)  # vital ל-pathים יחסיים
    out_dir = ROOT / "output"
    if not out_dir.exists():
        print("output/ ריק. הרץ קודם חילוץ.")
        return

    print("=" * 70)
    print("בקרת איכות חילוץ עמלות (QA)")
    print("=" * 70)

    all_fees = {}
    for f in sorted(out_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        bank = d["display_name"]
        for fk, v in d["fees"].items():
            all_fees.setdefault(fk, []).append((bank, v))

            # בדיקה 1: אחוז חריג בעמלת ש"ח
            fee_def = FEE_BY_KEY.get(fk)
            if not fee_def:
                continue
            if (fee_def.unit == "ILS" and v["price_unit"] == "percent"
                and v["price_value"] and v["price_value"] >= 50):
                add("גבוהה", bank, fk,
                    f"אחוז חריג בעמלת ₪ (יחידת סכמה={fee_def.unit})",
                    f"{v['price_value']}% — {v['price_text'][:50]}")

            # בדיקה 2: ערך גבוה מאוד (אאוטליר)
            if v["price_value"] and v["price_unit"] == "ILS" and v["price_value"] > 10000:
                add("בינונית", bank, fk,
                    f"ערך גבוה מאוד (>10k ₪) - ייתכן מינ'/מקס' שנקלט כתעריף",
                    f"{v['price_value']} ₪")

            # בדיקה 3: ציון נמוך
            if v["match_score"] < 85:
                add("נמוכה", bank, fk,
                    f"ציון התאמה נמוך ({v['match_score']}/100)",
                    f"label: {v['source_label'][:50]}")

            # בדיקה 4: מחיר חסר
            if v["price_value"] is None and not v["price_text"]:
                add("בינונית", bank, fk, "מחיר ריק לחלוטין", "—")

    # בדיקה 5: ערכים זהים בין בנקים (חשד להעתקה / טעות חילוץ)
    for fk, vals in all_fees.items():
        if len(vals) < 3:
            continue
        prices = [v["price_value"] for _, v in vals if v["price_value"]]
        if len(prices) >= 3:
            # אם 3+ בנקים מציגים בדיוק אותו ערך - חשד
            from collections import Counter
            most = Counter(prices).most_common(1)[0]
            if most[1] >= 3 and most[0] > 0:
                same_banks = [b for b, v in vals if v["price_value"] == most[0]]
                if len(same_banks) >= 3:
                    # זה לא ממש חשד אם זה תעריף בפיקוח
                    fee_def = FEE_BY_KEY.get(fk)
                    if fee_def and not fee_def.regulated:
                        add("מידע", same_banks[0], fk,
                            f"3+ בנקים מציגים אותו ערך ({most[0]}) — ייתכן וזה תעריף שוק או טעות חילוץ. בנקים: {', '.join(same_banks)}",
                            f"{most[0]}")

    # סיכום
    print(f"\nסה\"כ {len(SUSPICIOUS)} סימנים חשודים:")
    from collections import Counter
    by_sev = Counter(s["חומרה"] for s in SUSPICIOUS)
    for sev, n in by_sev.most_common():
        print(f"  {sev}: {n}")

    # ייצוא
    if "--export" in sys.argv:
        try:
            idx = sys.argv.index("--export")
            out_path = sys.argv[idx + 1]
        except (ValueError, IndexError):
            out_path = "qa_report.csv"

        import csv
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            if SUSPICIOUS:
                w = csv.DictWriter(f, fieldnames=list(SUSPICIOUS[0].keys()))
                w.writeheader()
                w.writerows(SUSPICIOUS)
        print(f"\nנשמר: {out_path}")
    else:
        print("\nדוגמאות:")
        for s in SUSPICIOUS[:15]:
            print(f"  [{s['חומרה']}] {s['בנק']} | {s['עמלה'][:35]}: {s['סיבה'][:60]}")
        print("\nלייצוא מלא: python qa_check.py --export qa_report.csv")


if __name__ == "__main__":
    main()
