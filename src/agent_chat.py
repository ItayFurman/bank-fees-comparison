"""
שיכבת LLM Chat לסוכן התאימות — גרסה משופרת.

מצב A — עם Anthropic Claude API: תשובות חכמות עם הקשר רגולטורי מלא.
מצב B — בלי מפתח: תבניות מבוססות-מכתב המפקח + כללי העמלות.
"""
from __future__ import annotations
import os
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from .compliance_agent import (ComplianceFinding, RISK_CATEGORIES, MEMORY_DIR)
from .security import safe_id, log_security_event
from .agent_tools import classify_intent, run_tool, AGENT_TOOLS

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ============================================================================
# פרומפט מערכת מקצועי
# ============================================================================

SYSTEM_PROMPT = """אתה סוכן ניטור תאימות רגולטורית של תעריפוני בנקים בישראל.
ידיעותיך מבוססות על שני מקורות בלבד שיש לך גישה אליהם:

1. **כללי הבנקאות (שירות ללקוח) (עמלות), התשס"ח-2008** — פורסם בנבו.
   כולל תוספת ראשונה (תעריפון אחיד) עם 15 חלקים, 5 תוספות, ו-5 נספחים.
   הסעיפים הרלוונטיים בחוק הבנקאות (שירות ללקוח), התשמ"א-1981:
   • 9ט(ד) — איסור גביית עמלות שונות לאותו שירות
   • 9ט(ה) — אישור מפקח להוספת שירות חדש
   • 9יג-9יד — אישור מפקח להעלאת תעריף בשירות בר-פיקוח
   • 9טו — דיווח 30 יום מראש בשירות שאינו בר-פיקוח

2. **מכתב המפקח על הבנקים, סימוכין 25LM5593, מתאריך 10.12.2025** —
   "עדכון מתכונת הפניה לפיקוח על הבנקים אודות שינויים בתעריפון העמלות".
   הבהרות מרכזיות:
   • חלק 9 לתעריפון המלא ("שירותים מיוחדים") דורש אישור מפקח מ-12.12.2024
     בהתאם לעמדה בת"צ 37816-09-19 סמוחה נ' בנק הפועלים.
   • שדה ההערות בתעריפון אסור לעריכה — לפי ת"צ 51664-12-20 + 51676-12-20
     סמוחה וגוטמן נ' הפועלים, לאומי, דיסקונט, מזרחי (25.11.2024).
   • הוצאות צד שלישי (חלק 11) חייבות להופיע גם בחלק 11 וגם לצד השירות.

תפקידך בדיון עם הבוחן:
א) לבחון ממצא חשוד ולקבוע אם זו עבירה אמיתית.
ב) להסביר את הבסיס המשפטי בצורה מקצועית ותמציתית.
ג) להמליץ על פעולה — חקירה / פנייה / סיווג כ-false-positive.
ד) ללמוד מ-verdict-ים שהבוחן נתן בעבר.

עקרונות:
• ענה בעברית מקצועית — 4-7 משפטים בכל תשובה.
• צטט סעיפי חוק/כללים/פסיקה במדויק — אל תמציא.
• אם מידע חסר — שאל את הבוחן שאלות מדויקות.
• הצע שלבים פרקטיים לבדיקה.
• זכור: יש לקחת בחשבון את הלחץ הציבורי על הפיקוח לאחר פסיקות סמוחה.
"""


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class Conversation:
    finding_id: str
    messages: list[ChatMessage] = field(default_factory=list)

    def to_dict(self):
        return {
            "finding_id": self.finding_id,
            "messages": [{"role": m.role, "content": m.content,
                          "timestamp": m.timestamp} for m in self.messages],
        }


# ============================================================================
# תבניות מייל ייחודיות לכל קטגוריית סיכון
# ============================================================================

EMAIL_TEMPLATES: dict[str, str] = {
    "R1": """\
אל: לשכת המפקח על הבנקים — היחידה לאישור שירותים חדשים
מאת: בוחן תאימות תעריפונים
תאריך: {date}
נושא: בקשת בחינה — שירות לא מוכר בתעריפון {bank}

לכבוד הצוות,

במסגרת ניטור תעריפוני התאגידים הבנקאיים מול כללי הבנקאות (שירות ללקוח)
(עמלות), התשס"ח-2008, זוהה בתעריפון {bank} פריט שאינו ניתן להתאמה
לאף שירות הקבוע בתוספת הראשונה לכללים.

**פרטי הממצא:**
• תאגיד בנקאי: {bank}
• פריט בתעריפון: "{bank_quote}"
• עמוד ב-PDF: {page}
• חומרה: {severity}

**ההיבט המשפטי:**
לפי סעיף 9ט(ה) לחוק הבנקאות (שירות ללקוח), נדרש אישור המפקח להוספת
שירות חדש לתעריפון המלא, ופרסום ברשומות על ידי הנגיד. מכתב המפקח
25LM5593 (10.12.2025), חלק ראשון, סעיף 1, מפרט את הנתונים הנדרשים
לבקשה.

**סיכום שיחת הבוחן:**
{summary}

**פעולה מבוקשת:**
1. בחינה האם הבנק הגיש בקשה רשמית להוספת השירות.
2. ככל שלא — שקלו פתיחת תיק חקירה.
3. עדכון המערכת על תוצאות הבחינה.

בכבוד רב,
בוחן תאימות
""",

    "R2": """\
אל: לשכת המפקח על הבנקים — צוות תעריפונים
מאת: בוחן תאימות
תאריך: {date}
נושא: חשד להעלאת תעריף חורגת — {bank} — {fee_name}

לכבוד הצוות,

ניתוח השוואתי של תעריפי {fee_name} (קוד {fee_code}) ב-{bank_count}
בנקים העלה כי {bank} גובה תעריף החורג משמעותית מן השוק.

**הנתונים:**
• תעריף {bank}: ₪{bank_price}
• חציון השוק: ₪{median}
• יחס: ×{ratio}
• עמלה: {fee_name} (חלק {part}, סעיף {fee_code})

**ההיבט המשפטי:**
לפי סעיפים 9יג-9טו לחוק:
- שירות בר-פיקוח דורש אישור מפקח להעלאת תעריף.
- שירות שאינו בר-פיקוח דורש דיווח 30 יום מראש (סעיף 9טו).

מכתב המפקח 25LM5593 (חלק ראשון, סעיף 2) מבהיר כי חיווי "נרשם דיווח"
אינו מהווה אישור לעצם ההעלאה.

**ציטוט מהבנק:**
"{bank_quote}"

**סיכום הבוחן:**
{summary}

**פעולה מבוקשת:**
1. בדיקה מול מערכת הדיווח האם {bank} דיווח/קיבל אישור להעלאה.
2. אם לא — בחינת עיצום כספי.
3. בחינה אל מול תעריף היסטורי של אותו בנק.

בכבוד רב,
בוחן תאימות
""",

    "R3": """\
אל: לשכת המפקח על הבנקים
מאת: בוחן תאימות
תאריך: {date}
נושא: חשד לכפילות עמלות לאותו שירות — {bank}

לכבוד הצוות,

בתעריפון {bank} זוהו שני פריטים נפרדים שלכאורה מתייחסים לאותו שירות
מהותית — בעמלת {fee_name} (קוד {fee_code}).

**ההיבט המשפטי:**
סעיף 9ט(ד) לחוק הבנקאות אוסר במפורש גביית עמלות שונות בעד אותו
שירות. עבירה על סעיף זה מהווה עילה לתובענה ייצוגית.

**הפריטים שזוהו:**
{bank_quote}

**סיכום שיחת הבוחן:**
{summary}

**פעולה מבוקשת:**
1. אימות מול ה-PDF המקורי שאכן מדובר בשני פריטים נפרדים בתעריפון.
2. בחינה האם השירותים זהים מהותית או נבדלים בפועל.
3. אם זהות — דרישת תיקון מיידי + שקילת הצדקה לעיצום.

בכבוד רב,
בוחן תאימות
""",

    "R4": """\
אל: לשכת המפקח על הבנקים — צוות חלק 9
מאת: בוחן תאימות
תאריך: {date}
נושא: שירות בחלק 9 ללא אישור — {bank}

לכבוד הצוות,

בתעריפון {bank} זוהה פריט שמאפייניו תואמים לחלק 9 לתעריפון המלא
("שירותים מיוחדים"), אך לא נמצאה לו אסמכתא לאישור מפקח ופרסום ברשומות.

**הרקע המשפטי:**
לפי עמדת מאסדר בת"צ 37816-09-19 סמוחה נ' בנק הפועלים (פורסם
12.12.2024), הוספת שירותים לחלק 9 דורשת אישור מפקח לפי סעיף 9ט(ה)
לחוק, על אף ניסוח התיבה "לפי פירוט שיקבע התאגיד הבנקאי". מכתב המפקח
25LM5593 (חלק שני, סעיף 2) מעגן זאת מול המערכת הבנקאית.

**פרטי הפריט:**
• פריט בתעריפון: "{bank_quote}"
• עמוד ב-PDF: {page}

**סיכום הבוחן:**
{summary}

**פעולה מבוקשת:**
1. אימות שלא קיים אישור היסטורי לפני 12.12.2024 (יוצא מתחולה).
2. ככל שזה שירות שנוסף אחרי 12.12.2024 ללא אישור — חשיפה משפטית
   גבוהה. מומלץ פעולה מיידית.

בכבוד רב,
בוחן תאימות
""",

    "R5": """\
אל: לשכת המפקח על הבנקים
מאת: בוחן תאימות
תאריך: {date}
נושא: חשד לעריכת שדה ההערות בתעריפון — {bank} — {fee_name}

לכבוד הצוות,

בתעריפון {bank} זוהתה הערה חריגה בעמלת {fee_name} (קוד {fee_code})
שלכאורה אינה תואמת לשדה ההערות הקבוע בכללי העמלות.

**הרקע המשפטי:**
לפי עמדת המפקח בת"צ 51664-12-20 + 51676-12-20 סמוחה וגוטמן נ' בנק
הפועלים, בנק לאומי, בנק דיסקונט ובנק מזרחי (25.11.2024), שדה ההערות
בתעריפון המלא נקבע במדויק בכללי העמלות ואסור לתאגידים הבנקאיים לערוך
בו שינויים — גם אם השינוי מקורו בהסדר פשרה בתובענה ייצוגית. תיקון
הערות דורש פנייה לפיקוח לתיקון הכללים (מכתב המפקח 25LM5593, חלק שני,
סעיף 3).

**ההערה החריגה:**
"{bank_quote}"

**סיכום הבוחן:**
{summary}

**פעולה מבוקשת:**
1. השוואת ההערה לשדה ההערות הרשמי בכללי העמלות.
2. אם ההערה חורגת — דרישת הסרה והתאמה לכללים.
3. הסבר נוסף ללקוח יכול להימסר מחוץ לתעריפון (חוזר, אתר וכד').

בכבוד רב,
בוחן תאימות
""",

    "R6": """\
אל: לשכת המפקח על הבנקים — אגף חלק 11
מאת: בוחן תאימות
תאריך: {date}
נושא: חוסר גילוי הוצאות צד שלישי — {bank} — {fee_name}

לכבוד הצוות,

בניתוח השוואתי זוהה כי הוצאת צד שלישי '{fee_name}' מופיעה בתעריפונים
של בנקים מתחרים אך לא בתעריפון {bank}.

**הרקע המשפטי:**
לפי מכתב הפיקוח מ-16.2.2022 ומכתב 25LM5593 (חלק שני, סעיף 4),
הוצאות צד שלישי שגובה הבנק חייבות להופיע גם בחלק 11 וגם לצד השירות
הרלוונטי. אם ההוצאה אינה אחידה — חייב לשקף את העלות הממשית הצפויה.

**הנתונים:**
• בנקים שגובים: {present_at}
• בנקים שלא רשמו: {bank}

**ההיבט המשפטי:**
חוסר גילוי הוצאות צד ג' עלול להוות הטעיה ולגרור תובענה ייצוגית.

**סיכום הבוחן:**
{summary}

**פעולה מבוקשת:**
1. בירור האם {bank} מספק את השירות בכלל.
2. אם כן — בירור מדוע ההוצאה אינה רשומה בתעריפון.
3. דרישת רישום בהתאם.

בכבוד רב,
בוחן תאימות
""",

    "R7": """\
אל: צוות הפיקוח (פנימי)
מאת: בוחן תאימות
תאריך: {date}
נושא: בעיית איכות נתונים — {bank}

הודעה פנימית: ה-PDF של {bank} אינו ניתן לחילוץ אוטומטי בשל פונט CID
או פורמט תמונה. נדרש להשיג גרסה חלופית של התעריפון לפני ביצוע ניתוח
תאימות לבנק זה.

זוהי הערה טכנית, לא ליקוי משפטי.
""",
}


# ============================================================================
# Backend
# ============================================================================

class AgentChat:
    def __init__(self, api_key: str | None = None,
                 model: str = "claude-sonnet-4-5"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.use_llm = bool(self.api_key) and HAS_ANTHROPIC
        self.model = model
        if self.use_llm:
            self.client = Anthropic(api_key=self.api_key)

    def status(self) -> str:
        if self.use_llm:
            return f"🟢 LLM פעיל ({self.model})"
        if not HAS_ANTHROPIC:
            return "🟡 חסרה חבילת `anthropic`. עובד במצב תבניות+כלים."
        return "🟡 אין ANTHROPIC_API_KEY. עובד במצב תבניות+כלים."

    # ----- שיח חופשי עם כלים אקטיביים -----

    def free_chat(self, user_msg: str, by_bank: dict,
                   history: list[ChatMessage] | None = None) -> str:
        """
        שיח חופשי — לא תלוי ב-finding ספציפי.
        מנסה קודם לזהות intent וקרוא לכלי. אם לא הצליח, נופל ל-LLM/template.
        """
        # 1. נסה לזהות intent ולהפעיל כלי
        intent = classify_intent(user_msg)
        if intent:
            tool_name, kwargs = intent
            result = run_tool(by_bank, tool_name, **kwargs)
            log_security_event("free_chat_tool",
                                f"tool={tool_name} args={kwargs}",
                                severity="info")
            return result

        # 2. אם LLM זמין - שלח שאלה כללית עם רשימת הכלים
        if self.use_llm:
            try:
                return self._llm_free_chat(user_msg, by_bank, history)
            except Exception as e:
                pass

        # 3. fallback: הצע למשתמש את הכלים הזמינים
        tools_help = "\n".join(f"• **{t.name}**: {t.description}"
                                for t in AGENT_TOOLS)
        return (f"לא זיהיתי את השאלה. אלה הכלים הזמינים:\n\n{tools_help}\n\n"
                f"שאלות לדוגמה:\n"
                f"• 'אילו בנקים יש במערכת?'\n"
                f"• 'השווה פעולה על ידי פקיד'\n"
                f"• 'סכם בנק לאומי'\n"
                f"• 'הראה 5 ממצאים הכי חריגים'\n"
                f"• 'מי הכי זול בעמלות עו\"ש?'")

    def _llm_free_chat(self, user_msg: str, by_bank: dict,
                        history: list[ChatMessage] | None = None) -> str:
        """שיח חופשי עם LLM - כולל תיאור הכלים והנתונים הזמינים."""
        tools_desc = "\n".join(f"- {t.name}: {t.description}"
                                 for t in AGENT_TOOLS)
        bank_summary = f"במערכת יש נתונים מ-{len(by_bank)} בנקים."

        sys_prompt = SYSTEM_PROMPT + (
            f"\n\nאתה משוחח כעת בשיח חופשי. הנתונים הזמינים:\n"
            f"{bank_summary}\n\nכלים שאתה יכול להציע למשתמש להפעיל:\n"
            f"{tools_desc}\n\n"
            f"אם הבוחן שואל שאלה שדורשת חישוב — ענה במה לעשות. אל תמציא נתונים."
        )

        msgs = []
        if history:
            for m in history[-10:]:  # 10 הודעות אחרונות
                msgs.append({"role": m.role, "content": m.content})
        msgs.append({"role": "user", "content": user_msg})

        resp = self.client.messages.create(
            model=self.model, max_tokens=800,
            system=sys_prompt, messages=msgs,
        )
        return resp.content[0].text

    # ----- API ראשי -----

    def respond(self, finding: ComplianceFinding, conv: Conversation,
                user_msg: str, comparison: dict | None = None) -> str:
        if self.use_llm:
            try:
                return self._llm_respond(finding, conv, user_msg, comparison)
            except Exception as e:
                return self._template_respond(finding, user_msg, comparison,
                                              note=f"(LLM נכשל: {e}.)")
        return self._template_respond(finding, user_msg, comparison)

    def summarize(self, finding: ComplianceFinding, conv: Conversation) -> str:
        if self.use_llm:
            try:
                return self._llm_summarize(finding, conv)
            except Exception:
                pass
        return self._template_summarize(finding, conv)

    def draft_email(self, finding: ComplianceFinding, conv: Conversation,
                    summary: str = "") -> str:
        # תמיד נשתמש בתבנית הרשמית הייחודית לקטגוריה
        return self._render_email(finding, conv, summary)

    def suggest_followups(self, finding: ComplianceFinding) -> list[str]:
        """3 שאלות מומלצות לבוחן בכל ממצא."""
        base = [
            "למה זה ליקוי לפי החוק/המכתב?",
            "מה השלבים המעשיים לבדיקה מעמיקה?",
            "האם זה כנראה false-positive? למה?",
        ]
        if finding.risk_category == "R2_PRICE_HIKE_NO_REPORT":
            base[0] = "האם תעריף חורג מעיד בהכרח על הפרה?"
        elif finding.risk_category == "R4_PART9_SPECIAL_SERVICES":
            base[0] = "מה ההבדל בין שירות חלק 9 שאושר לפני 12.12.2024 לשנוסף אחרי?"
        elif finding.risk_category == "R5_MODIFIED_NOTES_FIELD":
            base[0] = "איזו הערה נחשבת 'שינוי' לעומת 'הסבר נוסף ללקוח'?"
        return base

    # ----- LLM -----

    def _make_finding_context(self, finding: ComplianceFinding,
                               comparison: dict | None = None) -> str:
        rc = RISK_CATEGORIES.get(finding.risk_category, {})
        ctx = textwrap.dedent(f"""\
            ## ממצא נבדק (ID {finding.finding_id})
            • קטגוריה: {rc.get('title','?')}
            • בסיס משפטי: {rc.get('basis','?')}
            • חשיפה: {rc.get('exposure','?')}
            • הסבר: {rc.get('explanation','')}

            ## פרטי הממצא
            • בנק: {finding.bank}
            • עמלה: {finding.fee_name} (קוד {finding.fee_code or 'לא ידוע'})
            • חלק: {finding.part or '-'}
            • חומרה: {finding.severity}
            • כותרת: {finding.title}
            • תיאור: {finding.description}
            • ציטוט מהבנק: "{finding.bank_quote[:200]}"
            • עמוד ב-PDF: {finding.page_in_pdf}
            • ראיות: {json.dumps(finding.evidence, ensure_ascii=False)[:400]}

            ## פסיקת הבוחן עד כה
            • verdict: {finding.user_verdict or '(טרם נבדק)'}
            • הערות: {finding.user_notes or '—'}
        """)

        # הוספת השוואה רוחבית בין כל הבנקים על אותה עמלה
        if comparison and comparison.get("banks"):
            ctx += "\n## השוואה רוחבית של עמלה זו בכל הבנקים\n"
            stats = comparison.get("stats", {})
            unit = "%" if comparison.get("unit") == "percent" else "₪"
            ctx += f"• עמלה: {comparison['fee_name']} ({comparison['fee_code']})\n"
            ctx += f"• חלק: {comparison['part']}\n"
            ctx += f"• {'בפיקוח' if comparison.get('regulated') else 'לא בפיקוח'}\n"
            if "median" in stats:
                ctx += (f"• סטטיסטיקה: חציון {stats['median']:g}{unit}, "
                        f"מינ' {stats['min']:g}{unit}, "
                        f"מקס' {stats['max']:g}{unit}, "
                        f"זול ביותר: {stats.get('cheapest','—')}, "
                        f"יקר ביותר: {stats.get('most_expensive','—')}\n")
            ctx += "• פירוט פר-בנק:\n"
            for b in comparison["banks"]:
                if b["price"] is not None:
                    val = f"{b['price']:g}{unit}"
                else:
                    val = b.get("price_text", "?")[:40]
                marker = " ⬅" if b["bank"] == finding.bank else ""
                ctx += (f"   - {b['bank']}: {val}"
                        + (f" ({b['notes']})" if b.get('notes') else "")
                        + marker + "\n")
            if stats.get("missing"):
                ctx += f"• ללא נתון: {', '.join(stats['missing'])}\n"

        return ctx

    def _llm_respond(self, finding, conv, user_msg, comparison=None):
        ctx = self._make_finding_context(finding, comparison)
        if not conv.messages:
            msgs = [{"role": "user",
                     "content": ctx + "\n\n## שאלת הבוחן\n" + user_msg}]
        else:
            msgs = ([{"role": "user", "content": ctx}]
                    + [{"role": m.role, "content": m.content} for m in conv.messages]
                    + [{"role": "user", "content": user_msg}])

        resp = self.client.messages.create(
            model=self.model, max_tokens=900,
            system=SYSTEM_PROMPT, messages=msgs,
        )
        return resp.content[0].text

    def _llm_summarize(self, finding, conv):
        if not conv.messages:
            return self._template_summarize(finding, conv)
        transcript = "\n".join(
            f"[{m.role}] {m.content}" for m in conv.messages)
        prompt = (
            "סכם ב-3 משפטים פשוטים: (1) מהות הליקוי; (2) ההסבר הרגולטורי "
            "המרכזי; (3) הצעת פעולה. אל תוסיף פתיח/סיומת.\n\n"
            f"{self._make_finding_context(finding)}\n\n"
            f"## תמלול שיחה\n{transcript}"
        )
        resp = self.client.messages.create(
            model=self.model, max_tokens=350, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    # ----- תבניות -----

    def _format_comparison_block(self, comparison: dict | None,
                                  highlight_bank: str = "") -> str:
        """מעצב טבלת השוואה רוחבית כטקסט קריא."""
        if not comparison or not comparison.get("banks"):
            return ""
        unit = "%" if comparison.get("unit") == "percent" else "₪"
        stats = comparison.get("stats", {})
        lines = [
            f"**השוואה רוחבית — {comparison['fee_name']} "
            f"({comparison['fee_code']})**"
        ]
        if "median" in stats:
            lines.append(
                f"חציון: {stats['median']:g}{unit} · "
                f"מינ': {stats['min']:g}{unit} ({stats.get('cheapest','—')}) · "
                f"מקס': {stats['max']:g}{unit} ({stats.get('most_expensive','—')})"
            )
        lines.append("")
        for b in comparison["banks"]:
            if b["price"] is not None:
                val = f"{b['price']:g}{unit}"
            else:
                val = b.get("price_text", "?")[:30] or "ללא נתון"
            marker = " ⬅ הבנק הנבחן" if b["bank"] == highlight_bank else ""
            notes = f" · {b['notes']}" if b.get("notes") else ""
            lines.append(f"• **{b['bank']}**: {val}{notes}{marker}")
        if stats.get("missing"):
            lines.append(f"\n*ללא נתון:* {', '.join(stats['missing'])}")
        return "\n".join(lines)

    def _template_respond(self, finding, user_msg,
                           comparison: dict | None = None,
                           note: str = "") -> str:
        rc = RISK_CATEGORIES.get(finding.risk_category, {})
        msg = user_msg.lower()

        # שאלות על השוואה / בנקים אחרים — הדפסת ההשוואה
        if any(k in msg for k in ["השוואה", "בנקים אחרים", "מתחרים",
                                   "מה אחרים", "שאר הבנקים", "טווח",
                                   "טבלה", "כמה גובים"]):
            block = self._format_comparison_block(comparison, finding.bank)
            if block:
                return block + "\n\n" + (
                    "שאל אותי 'למה זה ליקוי?' להסבר משפטי, "
                    "או 'מה לעשות?' לפעולה מומלצת.")

        if any(k in msg for k in ["למה", "מדוע", "בסיס", "סעיף", "תקנה", "החוק"]):
            return textwrap.dedent(f"""\
                **בסיס משפטי:** {rc.get('basis','?')}

                {rc.get('explanation','')}

                **חשיפת התאגיד הבנקאי:** {rc.get('exposure','?')}

                {note}""")

        if any(k in msg for k in ["false", "טעות", "מטעה", "לא מדויק"]):
            return textwrap.dedent(f"""\
                בדוק את ההיבטים הבאים לפני סיווג כ-false-positive:

                1. **מקור הנתון:** האם הציטוט מהבנק ({finding.bank_quote[:80]}…)
                   תואם למה שמופיע ב-PDF בעמוד {finding.page_in_pdf}?

                2. **הקשר:** האם הפריט אכן שייך לקטגוריה {rc.get('title','?')}
                   או לאפיון אחר?

                3. **חריגים מותרים:** האם השירות נכלל בחריגי החוק
                   (אזרח ותיק, אדם עם מוגבלות, וכו')?

                אם מצאת שזה false-positive — סמן "❌ false-positive" כדי
                שהסוכן יזכור ולא ידווח בעתיד.{note}""")

        if any(k in msg for k in ["מה לעשות", "פעולה", "המלצה", "טיפול", "צעד"]):
            return textwrap.dedent(f"""\
                **פעולות מומלצות:**

                {finding.suggested_action or 'לא צוין.'}

                **אחרי האימות:**
                1. סמן verdict ("✅ אשר" / "❌ false-positive") — הסוכן ילמד.
                2. אם מאומת — הכן טיוטת מייל למפקח (כפתור למטה).
                3. השיחה הזאת תישמר ותהיה נגישה גם בעתיד.{note}""")

        if any(k in msg for k in ["דוגמ", "ציטו", "טקסט", "מקור"]):
            return textwrap.dedent(f"""\
                **הטקסט שזוהה מתעריפון הבנק (עמוד {finding.page_in_pdf}):**

                "{finding.bank_quote[:300]}"

                **הציטוט הרגולטורי הרלוונטי:**

                {finding.regulation_quote[:300]}{note}""")

        return textwrap.dedent(f"""\
            הממצא בקטגוריית **{rc.get('title','?')}** ברמת חומרה **{finding.severity}**.

            שאל אותי על:
            • "למה זה ליקוי לפי החוק?" — אסביר את הבסיס המשפטי.
            • "מה לעשות?" — פעולות מומלצות.
            • "האם זה false-positive?" — שיקולים נגד.
            • "תראה לי את המקור" — ציטוט ישיר מהבנק ומהכללים.{note}""")

    def _template_summarize(self, finding, conv) -> str:
        rc = RISK_CATEGORIES.get(finding.risk_category, {})
        n_msgs = len(conv.messages)
        return textwrap.dedent(f"""\
            **סיכום הממצא** (אחרי {n_msgs} הודעות בשיחה)

            1. **מהות:** {finding.title}
            2. **בסיס:** {rc.get('basis','?')}
            3. **המלצה:** {(finding.suggested_action or rc.get('exposure','-'))[:200]}
        """)

    def _render_email(self, finding, conv, summary) -> str:
        rc = RISK_CATEGORIES.get(finding.risk_category, {})
        template_key = rc.get("email_template", "R1")
        tmpl = EMAIL_TEMPLATES.get(template_key, EMAIL_TEMPLATES["R1"])

        # ערכים לתבנית
        ev = finding.evidence
        ctx = {
            "date": datetime.now().strftime("%d.%m.%Y"),
            "bank": finding.bank,
            "fee_name": finding.fee_name or "—",
            "fee_code": finding.fee_code or "—",
            "part": finding.part or "—",
            "severity": finding.severity,
            "bank_quote": finding.bank_quote[:300] or "(אין ציטוט ספציפי)",
            "page": finding.page_in_pdf if finding.page_in_pdf > 0 else "—",
            "summary": summary or "(טרם נוסח סיכום)",
            "bank_count": len(ev.get("all_banks", {})) or "—",
            "bank_price": ev.get("bank_price", "—"),
            "median": ev.get("market_median", "—"),
            "ratio": f"{ev.get('ratio', 0):.1f}" if ev.get("ratio") else "—",
            "present_at": ", ".join(ev.get("present_at", [])[:5]) or "—",
        }

        try:
            return tmpl.format(**ctx)
        except KeyError as e:
            # אם המפתח חסר בתבנית - השתמש ב-default
            return EMAIL_TEMPLATES["R1"].format(**ctx)


# ============================================================================
# שמירת שיחות
# ============================================================================

def _conv_path(finding_id: str) -> Path:
    """
    SECURITY: סניטיזציה של finding_id למניעת Path Traversal.
    finding_id יכול לבוא מתוך JSON שאוחסן בעבר; ייתכן שמישהו ערך אותו ל-'../../etc/passwd'.
    """
    sid = safe_id(finding_id)
    if sid != finding_id:
        log_security_event(
            "unsafe_finding_id_sanitized",
            f"orig={finding_id!r} sanitized={sid!r}",
            severity="warning",
        )
    target = MEMORY_DIR / "conversations" / f"{sid}.json"
    # Defense in depth: ודא שהיעד באמת בתוך conversations/
    try:
        target.resolve().relative_to((MEMORY_DIR / "conversations").resolve())
    except (ValueError, RuntimeError):
        # אם איכשהו נחרגנו - חזור לפדיפולט בטוח
        target = MEMORY_DIR / "conversations" / "default.json"
    return target


def load_conversation(finding_id: str) -> Conversation:
    p = _conv_path(finding_id)
    if not p.exists():
        return Conversation(finding_id=finding_id)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return Conversation(
        finding_id=raw["finding_id"],
        messages=[ChatMessage(**m) for m in raw["messages"]],
    )


def save_conversation(conv: Conversation):
    (MEMORY_DIR / "conversations").mkdir(parents=True, exist_ok=True)
    _conv_path(conv.finding_id).write_text(
        json.dumps(conv.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
