"""
כלים אקטיביים לסוכן — אפשרויות חיפוש/שאילתה שהסוכן יכול להפעיל בזמן שיח.

הסוכן (גם במצב LLM וגם במצב Template) יכול לקרוא לכלים האלה כדי לענות
על שאלות שדורשות מידע מהמערכת — לדוגמה:
  • "תראה לי את כל הליקויים של דיסקונט"
  • "מי הכי יקר בעמלת פנקס שיקים?"
  • "השווה ניהול חשבון בכל הבנקים"
  • "מהן 5 העמלות הכי חורגות?"
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable

from .compliance_agent import (load_findings, build_cross_bank_comparison,
                                RISK_CATEGORIES, ComplianceFinding,
                                bank_risk_scores, top_findings)
from .schema import CANONICAL_FEES, FEE_BY_KEY, PARTS_ORDER
from .normalizer import NormalizedFee
from .bank_profiles import PROFILES_BY_ID, PROFILES


# ============================================================================
# הגדרת כלי הסוכן
# ============================================================================

@dataclass
class AgentTool:
    name: str
    description: str   # מה הכלי עושה (לתיאור ב-prompt של LLM)
    handler: Callable  # פונקציה שמקבלת kwargs ומחזירה str


# ============================================================================
# הכלים בעצמם
# ============================================================================

def tool_list_banks(by_bank: dict, **kwargs) -> str:
    """רשימת בנקים עם מספר עמלות מזוהות לכל אחד."""
    if not by_bank:
        return "אין בנקים זמינים. הרץ חילוץ קודם."
    lines = ["**בנקים זמינים במערכת:**"]
    for bid, fees in sorted(by_bank.items(),
                              key=lambda x: -len(x[1])):
        name = (PROFILES_BY_ID[bid].display_name
                if bid in PROFILES_BY_ID else bid)
        lines.append(f"• **{name}** — {len(fees)} עמלות מזוהות")
    return "\n".join(lines)


def tool_compare_fee(by_bank: dict, fee_query: str = "", **kwargs) -> str:
    """השווה עמלה מסוימת בכל הבנקים. fee_query יכול להיות שם עמלה / קוד / חלק ממנו."""
    if not fee_query:
        return "ציין שם עמלה. לדוגמה: 'השווה פעולה על ידי פקיד'."

    # מצא fee_key מתאים
    q = fee_query.lower().strip()
    candidates = []
    for fee in CANONICAL_FEES:
        if (q in fee.he_name.lower() or q in fee.code.lower()
            or fee.code == fee_query):
            candidates.append(fee)

    if not candidates:
        # נסה כללי יותר
        words = re.findall(r"\w+", q)
        for fee in CANONICAL_FEES:
            if any(w in fee.he_name.lower() for w in words if len(w) > 2):
                candidates.append(fee)

    if not candidates:
        return f"לא מצאתי עמלה בשם '{fee_query}'. שאל אותי 'אילו עמלות יש?' לרשימה."

    fee = candidates[0]
    comp = build_cross_bank_comparison(by_bank, fee.key)
    if not comp.get("banks"):
        return f"לעמלת '{fee.he_name}' אין נתונים באף בנק."

    unit = "%" if comp["unit"] == "percent" else "₪"
    stats = comp["stats"]
    lines = [
        f"**{fee.he_name}** (קוד `{fee.code}`, {fee.part})",
        ""
    ]
    if "median" in stats:
        lines.append(
            f"📊 חציון: {stats['median']:g}{unit} · "
            f"מינ': {stats['min']:g}{unit} ({stats.get('cheapest','')}) · "
            f"מקס': {stats['max']:g}{unit} ({stats.get('most_expensive','')})"
        )
    lines.append("")
    for b in comp["banks"]:
        if b["price"] is not None:
            val = f"{b['price']:g}{unit}"
        else:
            val = b.get("price_text", "?")[:30]
        notes = f" · {b['notes']}" if b.get("notes") else ""
        lines.append(f"• **{b['bank']}**: {val}{notes}")
    if stats.get("missing"):
        lines.append(f"\n*ללא נתון:* {', '.join(stats['missing'])}")

    return "\n".join(lines)


def tool_bank_summary(by_bank: dict, bank_name: str = "", **kwargs) -> str:
    """סיכום של בנק ספציפי - עמלות מזוהות, ציון סיכון, ממצאי תאימות."""
    if not bank_name:
        return "ציין שם בנק. לדוגמה: 'סכם דיסקונט'."

    # מצא bank_id
    target_bid = None
    target_name = None
    for bid, prof in PROFILES_BY_ID.items():
        if bank_name in prof.display_name or prof.display_name in bank_name:
            target_bid = bid
            target_name = prof.display_name
            break

    if not target_bid or target_bid not in by_bank:
        return f"לא מצאתי את הבנק '{bank_name}'."

    fees = by_bank[target_bid]
    findings = [f for f in load_findings() if f.bank == target_name]
    scores = bank_risk_scores(load_findings())
    bank_score = scores.get(target_name, {"score": 0, "level": "נמוך",
                                            "findings_count": 0})

    lines = [
        f"## 🏦 {target_name}",
        f"• עמלות מזוהות: **{len(fees)}**",
        f"• ציון סיכון: **{bank_score['score']}** ({bank_score['level']})",
        f"• ממצאים: {len(findings)}",
        "",
    ]

    # פירוט לפי חלקים
    from collections import Counter
    parts_count = Counter()
    for fk in fees:
        fd = FEE_BY_KEY.get(fk)
        if fd:
            parts_count[fd.part] += 1
    if parts_count:
        lines.append("**עמלות לפי חלק:**")
        for part, n in parts_count.most_common():
            lines.append(f"• {part}: {n}")
        lines.append("")

    if findings:
        from collections import Counter
        cat_counter = Counter(f.risk_category for f in findings)
        lines.append("**ממצאים לפי קטגוריה:**")
        for cat, n in cat_counter.most_common():
            t = RISK_CATEGORIES.get(cat, {}).get("title", cat)
            lines.append(f"• {t}: {n}")

    return "\n".join(lines)


def tool_top_outliers(n: int = 5, by_bank: dict | None = None, **kwargs) -> str:
    """N הממצאים החריגים ביותר במערכת."""
    findings = top_findings(load_findings(), n=n)
    if not findings:
        return "✓ אין ממצאים פתוחים."

    lines = [f"## 🎯 {len(findings)} הממצאים החמורים ביותר", ""]
    for i, f in enumerate(findings, start=1):
        rc = RISK_CATEGORIES.get(f.risk_category, {})
        sev_emoji = {"קריטית": "🔴", "גבוהה": "🟠",
                      "בינונית": "🟡", "נמוכה": "🟢"}.get(f.severity, "⚪")
        lines.append(
            f"**#{i}** {sev_emoji} [{rc.get('short','?')}] **{f.bank}** — "
            f"{f.title[:80]}"
        )
    return "\n".join(lines)


def tool_list_fees(part_filter: str = "", by_bank: dict | None = None, **kwargs) -> str:
    """רשימת כל העמלות הקנוניות (אופציונלית מסוננות לפי חלק)."""
    fees = CANONICAL_FEES
    if part_filter:
        q = part_filter.lower()
        fees = [f for f in fees if q in f.part.lower()]
    if not fees:
        return f"לא מצאתי עמלות בחלק '{part_filter}'."

    lines = [f"## עמלות קנוניות ({len(fees)} פריטים)", ""]
    current_part = None
    for fee in fees:
        if fee.part != current_part:
            current_part = fee.part
            lines.append(f"\n### {fee.part}")
        flag = " 🛡️" if fee.regulated else ""
        lines.append(f"• `{fee.code}` {fee.he_name}{flag}")
    return "\n".join(lines)


def tool_findings_by_bank(bank_name: str = "", by_bank: dict | None = None, **kwargs) -> str:
    """כל ממצאי התאימות של בנק ספציפי."""
    if not bank_name:
        return "ציין שם בנק."
    all_findings = load_findings()
    findings = [f for f in all_findings if bank_name in f.bank
                or f.bank in bank_name]
    if not findings:
        return f"לא נמצאו ממצאים עבור '{bank_name}'."

    lines = [f"## ממצאי תאימות של {findings[0].bank}", ""]
    from collections import defaultdict
    by_cat = defaultdict(list)
    for f in findings:
        by_cat[f.risk_category].append(f)
    for cat, items in by_cat.items():
        rc = RISK_CATEGORIES.get(cat, {})
        lines.append(f"\n### {rc.get('title', cat)} ({len(items)})")
        for f in items[:5]:
            sev_emoji = {"קריטית": "🔴", "גבוהה": "🟠",
                          "בינונית": "🟡", "נמוכה": "🟢"}.get(f.severity, "⚪")
            lines.append(f"• {sev_emoji} {f.title[:90]}")
        if len(items) > 5:
            lines.append(f"  ... ועוד {len(items) - 5}")
    return "\n".join(lines)


def tool_cheapest_in_part(by_bank: dict, part_query: str = "", **kwargs) -> str:
    """איזה בנק הכי זול בחלק מסוים?"""
    if not part_query:
        return "ציין חלק. למשל: 'מי הכי זול בחלק 1?' או 'בעו\"ש'."

    q = part_query.lower().strip()
    matching_parts = [p for p in PARTS_ORDER if q in p.lower()]
    if not matching_parts:
        return f"לא מצאתי חלק שמתאים ל-'{part_query}'."
    part = matching_parts[0]

    # ספור כמה פעמים כל בנק היה הכי זול
    wins_by_bank = {}
    fees_compared = 0
    for fee in CANONICAL_FEES:
        if fee.part != part:
            continue
        comp = build_cross_bank_comparison(by_bank, fee.key)
        stats = comp.get("stats", {})
        if "cheapest" in stats:
            wins_by_bank[stats["cheapest"]] = wins_by_bank.get(stats["cheapest"], 0) + 1
            fees_compared += 1

    if not wins_by_bank:
        return f"אין נתונים מספיקים להשוואה ב-{part}."

    lines = [f"## הזולים ביותר ב-{part}", "",
              f"השוואה על {fees_compared} עמלות:", ""]
    for bank, wins in sorted(wins_by_bank.items(), key=lambda x: -x[1]):
        lines.append(f"• **{bank}**: זול ביותר ב-{wins} עמלות")
    return "\n".join(lines)


# ============================================================================
# Registry
# ============================================================================

AGENT_TOOLS: list[AgentTool] = [
    AgentTool("list_banks",
               "מציג רשימת בנקים זמינים עם מספר עמלות מזוהות לכל אחד.",
               tool_list_banks),
    AgentTool("compare_fee",
               "משווה עמלה ספציפית בכל הבנקים. פרמטר: fee_query (שם או קוד עמלה).",
               tool_compare_fee),
    AgentTool("bank_summary",
               "סיכום עמלות + ציון סיכון + ממצאים של בנק ספציפי. פרמטר: bank_name.",
               tool_bank_summary),
    AgentTool("top_outliers",
               "מציג את N הממצאים החמורים ביותר. פרמטר: n (ברירת מחדל 5).",
               tool_top_outliers),
    AgentTool("list_fees",
               "רשימת כל העמלות הקנוניות. פרמטר אופציונלי: part_filter.",
               tool_list_fees),
    AgentTool("findings_by_bank",
               "כל ממצאי התאימות של בנק ספציפי. פרמטר: bank_name.",
               tool_findings_by_bank),
    AgentTool("cheapest_in_part",
               "מציג איזה בנק הזול ביותר בחלק מסוים. פרמטר: part_query.",
               tool_cheapest_in_part),
]

TOOLS_BY_NAME = {t.name: t for t in AGENT_TOOLS}


# ============================================================================
# Intent classifier — בוחר את הכלי הנכון לפי השאלה
# ============================================================================

def classify_intent(user_msg: str) -> tuple[str, dict] | None:
    """
    מחזיר (tool_name, kwargs) או None אם לא זוהה כוונה.
    """
    msg = user_msg.lower().strip()

    # מי הכי יקר/זול
    if any(w in msg for w in ["מי הכי זול", "מי הזול", "הזול ביותר",
                                 "חלק", "בעו\"ש"]):
        # מצא איזה חלק
        for part in PARTS_ORDER:
            short = part.split(" - ")[-1].split()[0] if " - " in part else part
            if short.lower() in msg or part.lower() in msg:
                return "cheapest_in_part", {"part_query": part}
        return "cheapest_in_part", {"part_query": "חלק 1"}

    # רשימת בנקים
    if any(w in msg for w in ["רשימת בנקים", "אילו בנקים", "מה הבנקים",
                                "אילו בנקים יש"]):
        return "list_banks", {}

    # רשימת עמלות
    if any(w in msg for w in ["אילו עמלות", "רשימת עמלות", "מה העמלות"]):
        return "list_fees", {}

    # ממצאים של בנק
    for prof in PROFILES:
        if prof.display_name in user_msg:
            if any(w in msg for w in ["ממצאים", "ליקויים", "בעיות", "תאימות"]):
                return "findings_by_bank", {"bank_name": prof.display_name}
            if any(w in msg for w in ["סכם", "סיכום", "פירוט", "תראה לי"]):
                return "bank_summary", {"bank_name": prof.display_name}

    # ממצאים חריגים
    if any(w in msg for w in ["הכי חריגים", "ממצאים חמורים", "top",
                                "הקריטיים", "החמורים"]):
        n = 5
        m = re.search(r"\d+", msg)
        if m: n = min(20, int(m.group()))
        return "top_outliers", {"n": n}

    # השוואת עמלה ספציפית
    if any(w in msg for w in ["השווה", "השוואת", "כמה גובים", "מי גובה",
                                "תעריף של"]):
        # נסה לזהות את העמלה בשאלה
        for fee in CANONICAL_FEES:
            # מצא חפיפה במילים
            keys_in_fee = fee.he_name.lower().split()
            if any(k in msg for k in keys_in_fee if len(k) > 2):
                return "compare_fee", {"fee_query": fee.he_name}
        return "compare_fee", {"fee_query": user_msg}

    return None


def run_tool(by_bank: dict, tool_name: str, **kwargs) -> str:
    """מפעיל כלי לפי שם. מעביר by_bank לכלים שצריכים אותו."""
    tool = TOOLS_BY_NAME.get(tool_name)
    if not tool:
        return f"כלי לא ידוע: {tool_name}"
    try:
        # כל הכלים מקבלים by_bank כ-kwarg אופציונלי
        return tool.handler(by_bank=by_bank, **kwargs)
    except TypeError:
        # ננסה בלי by_bank
        try:
            return tool.handler(**kwargs)
        except Exception as e:
            return f"שגיאה בכלי {tool_name}: {e}"
    except Exception as e:
        return f"שגיאה בכלי {tool_name}: {e}"
