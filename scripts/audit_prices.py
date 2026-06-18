"""
בקרת איכות על מחירי העמלות שחולצו (output/*.json).
מסמן מקרים חשודים שבהם ייתכן שהסריקה לא קלטה נכון את המחיר:

  THRESHOLD : הערך שנקלט מופיע בטקסט מיד אחרי "מעל"/"עד" → כנראה סף-עסקה, לא מחיר.
  HIGH      : ערך גבוה חריג בש"ח (>= 5000) → לבדיקה ידנית.
  NONE      : עמלה הותאמה אך לא נקלט לה מחיר כלל.
  PCT_LEAK  : היחידה ש"ח אך בטקסט יש "%" לפני ערך ש"ח → ייתכן שאחוז הוא המחיר.

Run:  python scripts/audit_prices.py
ASCII-only headers so הקונסול לא נופל.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "output"

# fee_keys שלגיטימי שיהיה להם ערך גבוה בש"ח (לא נסמן כ-HIGH)
HIGH_OK = {"safe_deposit_box", "financial_accompaniment"}


def _num_after_threshold(value: float, text: str) -> bool:
    """True אם הערך מופיע מיד אחרי מעל/עד (סף-עסקה)."""
    t = text.replace(",", "")
    # מציג את הערך כמספר שלם או עשרוני
    n = f"{value:.0f}" if value == int(value) else f"{value:g}"
    pat = r"(?:מעל|עד\s*ל?|לפחות|לא\s*יותר\s*מ-?|מ-)\s*" + re.escape(n) + r"\b"
    return bool(re.search(pat, t))


def _pct_before_shekel(text: str) -> bool:
    t = text.replace(",", "")
    m_pct = re.search(r"\d+(?:\.\d+)?\s*%", t)
    m_ils = re.search(r"\d+(?:\.\d+)?\s*(?:₪|ש[\"׳']?ח)", t)
    if not m_pct:
        return False
    # אחוז שאינו הנחה/הטבה, ומופיע לפני ערך הש"ח
    after = t[m_pct.end():m_pct.end() + 12]
    if re.match(r"\s*(?:ה\s*נ\s*ח\s*ה|ה\s*ט\s*ב\s*ה)", after):
        return False
    return m_ils is None or m_pct.start() < m_ils.start()


def audit_file(path: Path) -> list[tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    flags: list[tuple[str, str, str]] = []
    for key, fee in data.get("fees", {}).items():
        val = fee.get("price_value")
        unit = fee.get("price_unit")
        text = fee.get("price_text") or ""
        name = fee.get("he_name") or key

        if val is None:
            flags.append(("NONE", key, name))
            continue
        if unit == "ILS" and _num_after_threshold(val, text):
            flags.append(("THRESHOLD", key, f"{name}  = {val}  | {text[:70]}"))
            continue
        if unit == "ILS" and val >= 5000 and key not in HIGH_OK:
            flags.append(("HIGH", key, f"{name}  = {val}  | {text[:70]}"))
            continue
        if unit == "ILS" and _pct_before_shekel(text):
            flags.append(("PCT_LEAK", key, f"{name}  = {val}  | {text[:70]}"))
    return flags


def main() -> int:
    files = sorted(OUT_DIR.glob("*.json"))
    grand = 0
    by_type: dict[str, int] = {}
    for f in files:
        flags = audit_file(f)
        bank = json.loads(f.read_text(encoding="utf-8")).get("display_name", f.stem)
        total = len(json.loads(f.read_text(encoding="utf-8")).get("fees", {}))
        if flags:
            print(f"\n=== {bank}  ({len(flags)} flags / {total} fees) ===")
            for kind, key, detail in flags:
                by_type[kind] = by_type.get(kind, 0) + 1
                grand += 1
                print(f"   [{kind:9s}] {detail}")
        else:
            print(f"\n=== {bank}  (clean / {total} fees) ===")
    print("\n" + "=" * 60)
    print(f"TOTAL FLAGS: {grand}")
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"   {k:9s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
