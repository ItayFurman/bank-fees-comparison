"""
סכמה קנונית מלאה לפי "כללי הבנקאות (שירות ללקוח) (עמלות), התשס"ח-2008"
ותוספותיו (נבו, 159a). מכסה את 15 חלקי התוספת הראשונה +
תוספות שניה-חמישית + 5 נספחים.

מבנה:
  • CANONICAL_FEES — רשימת FeeDef לכל פריט בתעריפון.
  • PARTS_INDEX     — מפתח חלק → תיאור החלק.
  • SUPPLEMENTS     — חמש התוספות הרשמיות.
  • APPENDICES      — חמשת הנספחים.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class FeeDef:
    key: str
    he_name: str
    code: str              # קוד רשמי, למשל "1(א)(2)" או "5(9)"
    part: str
    supplement: str = "תוספת ראשונה"    # ברירת מחדל: תעריפון מלא ליחיד/עסק קטן
    regulated: bool = False
    unit: str = "ILS"
    notes: str = ""

# ============ אינדקס חלקי התוספת הראשונה ============

P1  = "חלק 1 - חשבון עובר ושב"
P2  = "חלק 2 - מידע, הודעות והתראות"
P3  = "חלק 3 - אשראי"
P4  = "חלק 4 - ניירות ערך"
P5  = "חלק 5 - מטבע חוץ"
P6  = "חלק 6 - כרטיסי חיוב"
P7  = "חלק 7 - סחר חוץ"
P8  = "חלק 8 - עסקאות עתידיות"
P9  = "חלק 9 - שירותים מיוחדים"
P10 = "חלק 10 - יהלומים"
P11 = "חלק 11 - הוצאות צד שלישי"
P12 = "חלק 12 - סליקה של עסקאות בכרטיס חיוב"
P13 = "חלק 13 - שירותי ניכיון לבתי עסק"
P14 = "חלק 14 - אפליקציית תשלום"
P15 = "חלק 15 - שירותי ריכוז מידע פיננסי"

PARTS_ORDER: list[str] = [P1, P2, P3, P4, P5, P6, P7, P8, P9, P10,
                          P11, P12, P13, P14, P15]

PARTS_INDEX: dict[str, str] = {
    P1:  "שירותים נפוצים בעו\"ש, שירותים מיוחדים/עסקיים, ומסלולי עמלות.",
    P2:  "הודעות, התראות, מסמכים, דוחות, איתורים.",
    P3:  "הקצאת אשראי, ערבויות, שעבודים, הלוואות לדיור, פירעון מוקדם.",
    P4:  "קנייה/מכירה ני\"ע, דמי משמרת, קסטודיאן, העברות ני\"ע.",
    P5:  "חליפין, מזומן מט\"ח, שיקים, העברות, ימי ערך, כיסוי חובה.",
    P6:  "דמי כרטיס, טעינה, חליפי, עסקאות וביצועי מט\"ח, רכישה מחלפן.",
    P7:  "סחר חוץ (לפי פירוט שיקבע התאגיד).",
    P8:  "עסקאות עתידיות / בין-מטבעיות (לפי פירוט שיקבע התאגיד).",
    P9:  "שירותים מיוחדים — כספות, ירושות, ייעוץ פנסיוני, וכו'. "
         "** מ-12.12.2024 דורש אישור מפקח (ת\"צ סמוחה נ' הפועלים). **",
    P10: "יהלומים (לפי פירוט שיקבע התאגיד).",
    P11: "הוצאות צד שלישי המועברות ללקוח בעלות ממשית.",
    P12: "דמי ניהול חשבון סליקה, אימות, ביטול עסקה, החזר חיוב.",
    P13: "ניכיון שיקים לבתי עסק (לפי פירוט).",
    P14: "קבלת/ביצוע תשלום באפליקציה, דמי מנוי.",
    P15: "ריכוז וניתוח מידע פיננסי מגופים שונים.",
}

# ============ חמש התוספות ============

SUPPLEMENTS: dict[str, str] = {
    "תוספת ראשונה":  "תעריפון מלא ליחיד ולעסק קטן (חלקים 1-15)",
    "תוספת שניה":    "תעריפון מצומצם – עובר ושב",
    "תוספת שלישית":  "תעריפון משכנתאות (מצומצם)",
    "תוספת רביעית":  "תעריפון כרטיסי חיוב (מצומצם)",
    "תוספת חמישית":  "תעריפון סליקה של עסקאות בכרטיס חיוב",
}

# ============ חמשת הנספחים ============

APPENDICES: dict[str, str] = {
    "נספח א'": "הטבות לקבוצות אוכלוסיה (אזרח ותיק, אדם עם מוגבלות וכו')",
    "נספח ב'": "שיקים מסחריים ומיוחדים",
    "נספח ג'": "טבלת ימי הערך",
    "נספח ד'": "דמי כרטיס לפי סוג הכרטיס",
    "נספח ה'": "הטבות בערוצי בנקאות בתקשורת",
}

# ============ העמלות הקנוניות ============

CANONICAL_FEES: list[FeeDef] = [

    # ╔════ חלק 1 - חשבון עובר ושב ════════════════════════════════╗
    # 1(א) שירותים נפוצים
    FeeDef("teller_transaction",        "פעולה על ידי פקיד",            "1(א)(2)",  P1, regulated=True,
           notes="הפקדה/משיכה מזומן, תדפיס, העברה, פדיון/הפקדת שיק, "
                 "תשלום שובר, פריטה. אזרח ותיק / אדם עם מוגבלות זכאי "
                 "ל-4 פעולות פקיד בחודש במחיר ערוץ ישיר."),
    FeeDef("direct_channel_transaction","פעולה בערוץ ישיר",              "1(א)(3)",  P1, regulated=True,
           notes="פטור על שאילתות באינטרנט/IVR/חיוב מיידי בכרטיס. "
                 "ביטול הרשאה לפני 6 חיובים – עד 6 פעולות ערוץ ישיר."),
    FeeDef("check_book",                "פנקס שיקים (רגיל / מיוחד)",      "1(א)(4)",  P1, regulated=True),
    FeeDef("bank_check",                "שיק בנקאי",                       "1(א)(7)",  P1),
    FeeDef("cash_handling_teller",      "טיפול במזומנים על ידי פקיד",      "1(א)(8)",  P1,
           notes="מטבעות לפי 100 / שטרות באחוז (מעל 10,000 ₪ ללקוח מזדמן)."),
    FeeDef("returned_charge_no_funds",  "החזרת חיוב מסיבת אין כיסוי / מוגבל / מעוקל", "1(א)(9)",  P1,
           notes="חל על שיק / הוראת קבע / הרשאה לחיוב."),
    FeeDef("returned_check_technical",  "חיוב מושך בהחזרת שיק מסיבה טכנית", "1(א)(10)", P1,
           notes="במקרה טעות הבנק – החזרה ב-5 ימי עסקים."),
    FeeDef("stop_charge_instruction",   "הוראה לביטול חיוב (שיק/הרשאה/הוראת קבע)", "1(א)(12)", P1,
           notes="ביטולים עוקבים – מקסימום 3 הוראות."),
    # 1(ב) שירותים מיוחדים/עסקיים
    FeeDef("salary_list_transfer",      "העברות ברשימה (כולל משכורת)",     "1(ב)(1)",  P1,
           notes="מקסימום 2 עמלות."),
    FeeDef("daily_offset_standing_order","הוראת קבע לקיזוז יומי",          "1(ב)(2)",  P1),
    FeeDef("deferred_check_handling",   "טיפול בשיק דחוי",                  "1(ב)(3)",  P1,
           notes="הפקדה/שינוי מועד/החזרה. החזרת שיקים אגב סגירה: עד 5 ₪."),
    FeeDef("returned_authorized_charge","חיוב מוטב בהחזרת חיוב על פי הרשאה", "1(ב)(4)",  P1,
           notes="רגיל / הצגה חוזרת (מההחזרה השנייה)."),
    FeeDef("rtgs_transfer",             "העברה במערכת זה\"ב (RTGS) לבנק אחר", "1(ב)(5)",  P1,
           notes="עד 1 מ' ₪: לא יעלה על מחיר פעולת פקיד אחת."),
    FeeDef("financial_accompaniment",   "ליווי פיננסי",                     "1(ב)(6)",  P1, unit="percent"),
    # 1(ג) מסלולים
    FeeDef("track_basic",               "מסלול בסיסי",                     "1(ג)(1)",  P1, regulated=True,
           notes="עד 1 פעולת פקיד + 10 ערוץ ישיר בחודש."),
    FeeDef("track_extended",            "מסלול מורחב",                      "1(ג)(2)",  P1, regulated=True,
           notes="עד 10 פקיד + 50 ערוץ ישיר בחודש."),
    FeeDef("track_extended_plus",       "מסלול מורחב פלוס",                 "1(ג)(3)",  P1, regulated=True,
           notes="כמו מורחב + שירותים נוספים לפי החלטת התאגיד."),

    # ╔════ חלק 2 - מידע, הודעות והתראות ══════════════════════════╗
    FeeDef("notices",                   "הודעות (פיגור / התראה / שיקים ללא כיסוי)", "2(א)(1)", P2, regulated=True),
    FeeDef("attorney_warning_letter",   "מכתב התראה של עורך דין",            "2(א)(2)",  P2),
    FeeDef("document_print",            "הפקה/הדפסה של מסמכים מהמאגר הממוחשב", "2(א)(3)", P2,
           notes="לבקשה + לעמוד. אסור לגבות עבור הודעה אחת בששת חודשי "
                 "סגירת חשבון."),
    FeeDef("standard_reports",          "דוחות סטנדרטיים",                  "2(א)(4)(א)", P2, regulated=True,
           notes="אישור יתרה לפני פירעון מוקדם של הלוואה – פטור."),
    FeeDef("info_collection_reports",   "דוחות הכרוכים באיסוף מידע",         "2(א)(4)(ב)", P2,
           notes="מידע היסטורי על ריביות/שערים/מכתב המלצה."),
    FeeDef("document_search",           "איתור מסמכים בארכיון",             "2(א)(5)",  P2),
    FeeDef("account_search",            "איתור חשבונות",                    "2(א)(6)",  P2),
    FeeDef("info_in_communication",     "קבלת מידע בתקשורת (פקס/SMS/אימייל)", "2(ב)(1)", P2,
           notes="עד 3 עמלות לפי פירוט."),
    FeeDef("info_magnetic_media",       "מידע במדיה מגנטית/אלקטרונית",       "2(ב)(2)",  P2),
    FeeDef("special_frequency_statements","הפקה ומשלוח דף תנועות בתדירות מיוחדת", "2(ב)(3)", P2),
    FeeDef("direct_computer_access",    "גישה ישירה למחשב הבנק",            "2(ב)(4)",  P2),

    # ╔════ חלק 3 - אשראי ══════════════════════════════════════════╗
    FeeDef("credit_allocation_individual","הקצאת אשראי - יחיד",             "3(א)(1)",  P3,
           notes="רבעוני, נגבה רק באי-ניצול מסגרת."),
    FeeDef("credit_allocation_small_biz","הקצאת אשראי - עסק קטן",          "3(א)(1)",  P3, unit="percent"),
    FeeDef("credit_handling_loan",      "טיפול באשראי - הלוואות מעל 100,000 ₪", "3(א)(2)",  P3, unit="percent"),
    FeeDef("credit_handling_check_disc","טיפול באשראי - ניכיון שיקים מעל 50,000 ₪", "3(א)(2)", P3, unit="percent"),
    FeeDef("credit_handling_smb_facility","טיפול באשראי - מסגרת לעסק קטן",  "3(א)(2)",  P3, unit="percent"),
    FeeDef("mortgage_request",          "טיפול בבקשה להלוואה לדיור",         "3(א)(2א)", P3,
           notes="נגבית אחרי ביצוע עיקר ההליכים."),
    FeeDef("bank_guarantee_general",    "ערבות בנקאית כללית",               "3(א)(5)",  P3, unit="percent"),
    FeeDef("bank_guarantee_buyers",     "ערבות משתכנים לפי חוק המכר",        "3(א)(5)",  P3, unit="percent"),
    FeeDef("bank_guarantee_deposit",    "ערבות מובטחת בפיקדון כספי ספציפי",   "3(א)(5)",  P3),
    FeeDef("bank_guarantee_rent",       "ערבות שכירות מובטחת בפיקדון (עד 50,000 ₪)", "3(א)(5)", P3),
    FeeDef("guarantee_assignment",      "הסבת ערבות לפי חוק המכר",           "3(א)(6)",  P3),
    FeeDef("lien_registration",         "רישום שעבודים אצל רשם",            "3(א)(7)",  P3),
    FeeDef("lien_change_bank",          "שינוי שעבודים - בבנק",             "3(א)(8)",  P3),
    FeeDef("lien_change_registrar",     "שינוי שעבודים - אצל רשם",           "3(א)(8)",  P3),
    FeeDef("consent_lien_other_bank",   "הסכמה ליצירת שעבוד לבנק אחר",       "3(א)(9)",  P3, regulated=True),
    FeeDef("loan_terms_change",         "שינויים בהסכם הלוואה / תנאי ערבות",  "3(א)(10)(א)", P3,
           notes="תקופה, זהות לווים, מסלול, ריבית, הקפאה, מועדים."),
    FeeDef("mortgage_payment_date_change","שינוי מועד פירעון של הלוואה לדיור","3(א)(10)(ב)", P3,
           notes="עד 4 שינויים בשנה במחיר פעולת פקיד אחת (סעיף 9ג לחוק)."),
    FeeDef("mortgage_drag_loan",        "גרירת הלוואה לדיור",               "3(א)(11)", P3),
    FeeDef("mortgage_drag_grant",       "גרירת מענק",                        "3(א)(11)", P3),
    FeeDef("mortgage_drag_bridge",      "גרירת ערבות / פיקדון ביניים",        "3(א)(11)", P3),
    FeeDef("eligibility_certificate",   "הנפקה/חידוש תעודת זכאות",          "3(א)(12)", P3),
    FeeDef("early_repayment",           "פירעון מוקדם של הלוואה (עמלה תפעולית)", "3(א)(13)", P3),
    FeeDef("financial_accompaniment_credit","ליווי פיננסי (חלק 3)",          "3(ב)(1)",  P3, unit="percent"),

    # ╔════ חלק 4 - ניירות ערך ═════════════════════════════════════╗
    FeeDef("securities_buy_sell_il_stocks","קנייה/מכירה ני\"ע ישראליים - מניות/אג\"ח", "4(א)(1)",  P4, unit="percent",
           notes="פיצול לכמה ביצועים באותו יום – עמלת מינ' אחת ביום."),
    FeeDef("securities_buy_sell_il_makam","קנייה/מכירה - מילווה קצר מועד (מק\"מ)", "4(א)(1)",  P4, unit="percent"),
    FeeDef("securities_buy_sell_il_internet","קנייה/מכירה ני\"ע ישראליים - באינטרנט", "4(א)(1)(4)", P4, unit="percent",
           notes="שיעור מופחת לפעולה ישירה באינטרנט."),
    FeeDef("securities_maof_options",   "קנייה/מכירה/כתיבת אופציות מעו\"ף",   "4(א)(2)",  P4, unit="percent"),
    FeeDef("securities_maof_futures",   "קנייה/מכירה/כתיבת חוזים עתידיים מעו\"ף", "4(א)(3)", P4),
    FeeDef("securities_buy_sell_foreign","קנייה/מכירה ני\"ע בחו\"ל",          "4(א)(4)",  P4, unit="percent"),
    FeeDef("securities_custody_il",     "דמי ניהול ני\"ע נסחרים בארץ",        "4(א)(5)",  P4, unit="percent"),
    FeeDef("securities_custody_foreign","דמי ניהול ני\"ע נסחרים בחו\"ל",      "4(א)(5)",  P4, unit="percent"),
    FeeDef("securities_custody_unlisted","דמי ניהול ני\"ע שאינם נסחרים",      "4(א)(5)",  P4, unit="percent"),
    FeeDef("securities_transfer",       "העברת ני\"ע לחשבון אותו לקוח בגוף אחר", "4(א)(6)", P4, regulated=True,
           notes="בסגירת חשבון: עד 10 ₪ להעברה + הוצאות צד ג'."),
    FeeDef("securities_conversion",     "המרת אג\"ח/שטרי הון למניות, מימוש אופציות", "4(א)(7)", P4),
    FeeDef("securities_issuance_order", "טיפול בהזמנה של ני\"ע בהנפקה",       "4(ב)(1)",  P4, unit="percent"),
    FeeDef("trust_fund_distribution",   "עמלת הפצה מרוכש יחידת קרן נאמנות",   "4(ב)(2)",  P4),
    FeeDef("securities_lending",        "השאלת ני\"ע לצורך מכירה בחסר",        "4(ב)(3)",  P4),
    FeeDef("custodian_fee",             "עמלת קסטודיאן",                     "4(ב)(4)",  P4, unit="percent"),

    # ╔════ חלק 5 - מטבע חוץ ═══════════════════════════════════════╗
    FeeDef("fx_conversion",             "עמלת חליפין",                       "5(1)",     P5, unit="percent",
           notes="מקסימום 2 עמלות בפירוט הבנק."),
    FeeDef("fx_cash_deposit_withdraw",  "הפקדה/משיכת מזומן בחשבון מט\"ח",     "5(2)",     P5,
           notes="לפי הפרשי שער."),
    FeeDef("fx_cash_exchange",          "החלפת מזומן (שטרות בלא שערים/פגומים)", "5(3)",  P5, unit="percent"),
    FeeDef("fx_check_collection",       "גביית שיקים במטבע חוץ",              "5(4)",     P5, unit="percent"),
    FeeDef("fx_check_deposit_redeem",   "הפקדת/פדיון שיק מט\"ח / המחאות נוסעים", "5(5)",  P5),
    FeeDef("fx_travelers_check_sale",   "מכירת המחאות נוסעים",               "5(6)",     P5, unit="percent"),
    FeeDef("fx_bank_check",             "שיק בנקאי במט\"ח",                  "5(7)",     P5, unit="percent"),
    FeeDef("fx_check_handling",         "טיפול בשיק משוך על חשבון מט\"ח לגבייה", "5(8)",  P5),
    FeeDef("fx_transfer_abroad",        "העברת מט\"ח לחו\"ל ומחו\"ל",          "5(9)",     P5, unit="percent",
           notes="פטור: רנטות/פנסיות לנפגעי נאצים."),
    FeeDef("fx_transfer_local",         "העברת מט\"ח בארץ ומבנק אחר בארץ",     "5(10)",    P5, regulated=True,
           notes="לאותו לקוח – עד 10 ₪ בסגירת חשבון."),
    FeeDef("fx_value_days",             "ימי ערך (לפי פירוט בנספח)",          "5(11)",    P5),
    FeeDef("fx_auto_overdraft_cover",   "כיסוי אוטומטי של יתרת חובה מט\"ח",   "5(12)",    P5, unit="percent"),

    # ╔════ חלק 6 - כרטיסי חיוב ════════════════════════════════════╗
    FeeDef("debit_card_fee",            "דמי כרטיס",                         "6(1)",     P6,
           notes="לקוח עם כרטיס אשראי תקף באותו בנק – פטור בכרטיס "
                 "חיוב מיידי ל-36 חודשים מהנפקה. נספח ד': פירוט "
                 "לפי סוג."),
    FeeDef("card_topup_fee",            "דמי טעינה (כרטיס נטען)",            "6(1א)",    P6),
    FeeDef("card_deferred_payment",     "עמלת תשלום נדחה (עד 31.1.2015)",     "6(2)",     P6),
    FeeDef("card_charge_date_change",   "שינוי מועד חיוב",                    "6(3)",     P6),
    FeeDef("card_dispute_unjust",       "טיפול בהכחשה לא מוצדקת של עסקה",     "6(4)",     P6),
    FeeDef("card_early_repayment",      "פירעון מוקדם/מיידי של עסקאות",        "6(5)",     P6,
           notes="בביטול כרטיס אגב סגירה: תקרה 40 ₪."),
    FeeDef("card_replacement_regular",  "הנפקת כרטיס חליפי - רגילה",          "6(6)",     P6),
    FeeDef("card_replacement_express",  "הנפקת כרטיס חליפי - מיידית",          "6(6)",     P6),
    FeeDef("card_fx_transactions_usd",  "עסקאות מט\"ח - דולר/אירו",          "6(7)",     P6, unit="percent"),
    FeeDef("card_fx_transactions_other","עסקאות מט\"ח - מטבע אחר",            "6(7)",     P6, unit="percent"),
    FeeDef("card_atm_fx_usd",           "משיכת מזומן בדולר/אירו ממכשיר אוטומטי", "6(8)",  P6, unit="percent"),
    FeeDef("card_atm_fx_other",         "משיכת מזומן במטבע אחר ממכשיר אוטומטי", "6(8)", P6, unit="percent"),
    FeeDef("card_teller_fx_usd",        "משיכת מזומן בדולר/אירו בדלפק",       "6(8)",     P6, unit="percent"),
    FeeDef("card_teller_fx_other",      "משיכת מזומן במטבע אחר בדלפק",         "6(8)",     P6, unit="percent"),
    FeeDef("card_fx_same_currency",     "משיכת מזומן מט\"ח מחשבון באותו מטבע", "6(8)",   P6),
    FeeDef("card_fx_from_changer",      "רכישת מט\"ח מחלפן באמצעות כרטיס",     "6(9)",     P6),

    # ╔════ חלק 7 - סחר חוץ (לפי פירוט שיקבע התאגיד) ═══════════════╗
    FeeDef("trade_finance",             "סחר חוץ (לפי פירוט שיקבע התאגיד)",   "7",        P7,
           notes="לא נדרש אישור מפקח להוספת פריט, אך חובת דיווח לפי חוק."),

    # ╔════ חלק 8 - עסקאות עתידיות ═════════════════════════════════╗
    FeeDef("futures_transactions",      "עסקאות עתידיות / בין-מטבעיות (לפי פירוט)", "8", P8,
           notes="לפי פירוט שיקבע התאגיד."),

    # ╔════ חלק 9 - שירותים מיוחדים (** דורש אישור מפקח **) ════════╗
    FeeDef("post_holding",              "שמירת דואר בסניף",                  "9",        P9,
           notes="⚠ פסיקת ת\"צ 37816-09-19 (12.12.2024): מ-12.12.2024 "
                 "הוספת שירות לחלק 9 דורשת אישור מפקח ופרסום ברשומות."),
    FeeDef("safe_deposit_box",          "שכירת כספות",                       "9",        P9),
    FeeDef("notes_handling",            "טיפול בשטרות",                       "9",        P9),
    FeeDef("estate_handling",           "טיפול בירושות ועיזבונות",            "9",        P9),
    FeeDef("foreign_atm_other_card",    "משיכת מזומן ממכשיר מרוחק עם כרטיס לא של הבנק", "9", P9),
    FeeDef("rights_assignment",         "טיפול בהמחאת זכות",                  "9",        P9),
    FeeDef("pension_advisory",          "ייעוץ פנסיוני (חוק הפיקוח הפיננסי)",  "9",        P9),
    FeeDef("prepaid_card_atm_withdrawal","משיכה במכשיר אוטומטי בכרטיס נטען לא מקושר", "9", P9, unit="percent"),
    FeeDef("foreign_card_atm_withdrawal","משיכה במכשיר אוטומטי בכרטיס מחו\"ל",   "9",     P9),

    # ╔════ חלק 10 - יהלומים ═══════════════════════════════════════╗
    FeeDef("diamonds_services",         "שירותים ליהלומנים (לפי פירוט)",     "10",       P10),

    # ╔════ חלק 11 - הוצאות צד שלישי (חובת גילוי) ══════════════════╗
    FeeDef("third_registration_fees",   "אגרות רישום שונות",                 "11",       P11,
           notes="הוצאות צד שלישי – יש לציין גם בחלק 11 וגם לצד השירות."),
    FeeDef("third_appraiser",           "הערכת שמאי",                        "11",       P11),
    FeeDef("third_emi_insurance",       "ביטוח הלוואה לדיור (EMI)",          "11",       P11),
    FeeDef("third_notary_power",        "ייפוי כוח נוטריוני",                 "11",       P11),
    FeeDef("third_companies_registrar", "בדיקת רישומים ברשם החברות",          "11",       P11),
    FeeDef("third_land_registrar",      "בדיקת רישומים ברשם המקרקעין",         "11",       P11),
    FeeDef("third_returned_charge_bank","החזר שיק/הרשאה לטובת הבנק",          "11",       P11),
    FeeDef("third_correspondent_bank",  "הוצאות בנק קורספונדנט",              "11",       P11),
    FeeDef("third_broker_abroad",       "הוצאות ברוקר בחוץ לארץ",             "11",       P11),
    FeeDef("third_safe_insurance",      "ביטוח כספת",                        "11",       P11),
    FeeDef("third_abroad_mail",         "דואר לחו\"ל / משלוח כרטיס חליפי",    "11",       P11),
    FeeDef("third_registered_mail",     "דואר רשום",                          "11",       P11),
    FeeDef("third_card_reader_use",     "שימוש במכשירים לקריאת כרטיסי חיוב",   "11",       P11),
    FeeDef("third_fx_atm_abroad_teller","משיכת מזומן מט\"ח בחו\"ל בדלפק",      "11",       P11),

    # ╔════ חלק 12 - סליקה של עסקאות בכרטיס חיוב ═══════════════════╗
    FeeDef("clearing_active_biz_mgmt",  "דמי ניהול חשבון סליקה - בית עסק פעיל", "12(1)", P12,
           notes="בית עסק פעיל = שנסלקה לפחות עסקה אחת בחודש."),
    FeeDef("clearing_ecommerce_signup", "דמי הצטרפות של בית עסק אלקטרוני",    "12(2)",    P12),
    FeeDef("clearing_verify_insure",    "שירותי אימות פרטים וביטוח עסקה",      "12(3)",    P12),
    FeeDef("clearing_cancel_transaction","ביטול עסקה",                        "12(4)",    P12),
    FeeDef("clearing_chargeback",       "החזר חיוב (Chargeback)",            "12(5)",    P12),
    FeeDef("clearing_manual_voucher",   "עיבוד שובר ידני",                    "12(6)",    P12),
    FeeDef("clearing_fee",              "עמלת סליקה (לפי הסכם התקשרות)",      "12(7)",    P12, unit="percent"),

    # ╔════ חלק 13 - ניכיון לבתי עסק ═══════════════════════════════╗
    FeeDef("discount_services_biz",     "שירותי ניכיון לבתי עסק (לפי פירוט)", "13",       P13),

    # ╔════ חלק 14 - אפליקציית תשלום ═══════════════════════════════╗
    FeeDef("payment_app_receive",       "קבלת תשלום באפליקציה (מעבר לסף 25,000 ₪/שנה)", "14(א)(1)", P14,
           notes="לא ייגבה במקביל ל'פעולה בערוץ ישיר'. סף לא יפחת מ-25,000 ₪."),
    FeeDef("payment_app_send",          "ביצוע הוראת תשלום באפליקציה (מעבר לסף)", "14(א)(2)", P14,
           notes="לא ייגבה במקביל ל'פעולה בערוץ ישיר'."),
    FeeDef("payment_app_subscription",  "דמי מנוי לשירות באפליקציה",         "14(ב)",    P14,
           notes="טעון אישור מפקח."),

    # ╔════ חלק 15 - ריכוז וניתוח מידע פיננסי ══════════════════════╗
    FeeDef("financial_aggregator",      "שירותי ריכוז וניתוח מידע פיננסי",    "15",       P15,
           notes="חל רק על ריכוז ממספר גופים פיננסיים שונים."),
]

FEE_BY_KEY: dict[str, FeeDef] = {f.key: f for f in CANONICAL_FEES}

# ============ מילות מפתח לזיהוי ============

FEE_KEYWORDS: dict[str, list[str]] = {
    # חלק 1
    "teller_transaction":         ["פעולה על ידי פקיד", "פעולה ע\"י פקיד", "פעולת פקיד"],
    "direct_channel_transaction": ["פעולה בערוץ ישיר", "פעולה בערוצים ישירים", "פעולה אוטומטית"],
    "check_book":                 ["פנקס שיקים", "פנקס שקים", "הזמנת פנקס"],
    "bank_check":                 ["שיק בנקאי", "המחאה בנקאית", "ערבון בנקאי"],
    "cash_handling_teller":       ["טיפול במזומנים על ידי פקיד", "טיפול במזומן ע\"י פקיד"],
    "returned_charge_no_funds":   ["החזרת חיוב מסיבת אין כיסוי", "מסיבת אין כיסוי",
                                   "החזרה מסיבה של אין כיסוי"],
    "returned_check_technical":   ["חיוב מושך בהחזרת שיק מסיבה טכנית",
                                   "החזרת שיק - מושך", "חיוב מושך בהחזרת שיק"],
    "stop_charge_instruction":    ["הוראה לביטול חיוב", "ביטול שיק",
                                   "ביטול הוראת קבע", "ביטול הרשאה"],
    "salary_list_transfer":       ["העברות ברשימה", "העברת משכורת", "תשלום משכורת"],
    "daily_offset_standing_order":["הוראת קבע לקיזוז יומי", "קיזוז יומי"],
    "deferred_check_handling":    ["טיפול בשיק דחוי", "שיק דחוי",
                                   "החזרת שיקים דחויים למפקיד", "הפקדת שיק דחוי"],
    "returned_authorized_charge": ["חיוב מוטב בהחזרת חיוב", "הצגה חוזרת"],
    "rtgs_transfer":              ["העברה במערכת זה\"ב", "RTGS", "העברה בזמן אמת"],
    "financial_accompaniment":    ["ליווי פיננסי"],
    "track_basic":                ["מסלול בסיסי"],
    "track_extended":             ["מסלול מורחב"],
    "track_extended_plus":        ["מסלול מורחב פלוס"],

    # חלק 2
    "notices":                    ["הודעה על פיגור", "התראה", "הודעות"],
    "attorney_warning_letter":    ["מכתב התראה של עורך דין", "מכתב עורך דין"],
    "document_print":             ["הפקה/הדפסה של מסמכים", "הפקה או הדפסה של מסמכים",
                                   "תדפיס דף חשבון",
                                   "העתק דף חשבון", "הדפסת מסמכים", "מסמכים במאגר"],
    "standard_reports":           ["דוחות סטנדרטיים", "אישור יתרה",
                                   "פירוט תיק ניירות ערך", "אישור בעלות", "לוח סילוקין"],
    "info_collection_reports":    ["דוחות הכרוכים באיסוף מידע", "מידע היסטורי", "מכתב המלצה"],
    "document_search":            ["איתור מסמכים", "חיפוש מסמכים"],
    "account_search":             ["איתור חשבונות"],
    "info_in_communication":      ["קבלת מידע בתקשורת", "מידע בתקשורת"],
    "info_magnetic_media":        ["מידע במדיה מגנטית", "מידע אלקטרוני"],
    "special_frequency_statements":["דף תנועות בתדירות מיוחדת"],
    "direct_computer_access":     ["גישה ישירה למחשב"],

    # חלק 3
    "credit_allocation_individual":["הקצאת אשראי", "מסגרת אשראי", "טיפול במסגרת אשראי"],
    "credit_allocation_small_biz":["הקצאת אשראי לעסק קטן"],
    "credit_handling_loan":       ["טיפול באשראי ובביטחונות", "טיפול בהלוואה", "עמלת פתיחת תיק"],
    "credit_handling_check_disc": ["ניכיון שיקים"],
    "credit_handling_smb_facility":["מסגרת אשראי לעסק קטן"],
    "mortgage_request":           ["טיפול בבקשה להלוואה לדיור", "טיפול בהלוואת דיור"],
    "bank_guarantee_general":     ["ערבות בנקאית"],
    "bank_guarantee_buyers":      ["ערבות משתכנים", "חוק המכר"],
    "bank_guarantee_deposit":     ["ערבות מובטחת בפיקדון"],
    "bank_guarantee_rent":        ["ערבות שכירות"],
    "guarantee_assignment":       ["הסבת ערבות"],
    "lien_registration":          ["רישום שעבודים"],
    "lien_change_bank":           ["שינוי שעבודים בבנק"],
    "lien_change_registrar":      ["שינוי שעבודים אצל רשם"],
    "consent_lien_other_bank":    ["הסכמה ליצירת שעבוד לבנק אחר", "שעבוד לבנק אחר"],
    "loan_terms_change":          ["שינויים בהסכם ההלוואה", "שינוי בתנאי הלוואה"],
    "mortgage_payment_date_change":["שינוי מועד פירעון של הלוואה לדיור"],
    "mortgage_drag_loan":         ["גרירת הלוואה לדיור", "גרירת הלוואה"],
    "mortgage_drag_grant":        ["גרירת מענק"],
    "mortgage_drag_bridge":       ["גרירת ערבות", "פיקדון ביניים"],
    "eligibility_certificate":    ["תעודת זכאות"],
    "early_repayment":            ["פירעון מוקדם", "פדיון מוקדם", "עמלה תפעולית"],

    # חלק 4
    "securities_buy_sell_il_stocks":["קנייה ומכירה של ניירות ערך הנסחרים בבורסה בתל אביב", "הנסחרים בבורסה בתל אביב",
                                     "מניות ואגרות חוב", "ני\"ע בארץ"],
    "securities_buy_sell_il_makam":["מילווה קצר מועד", "מק\"מ"],
    "securities_buy_sell_il_internet":["באמצעות האינטרנט - מניות"],
    "securities_maof_options":    ["אופציות מעו\"ף"],
    "securities_maof_futures":    ["חוזים עתידיים במעו\"ף"],
    "securities_buy_sell_foreign":["קנייה ומכירה ני\"ע בחו\"ל", "קנייה/מכירה ניירות ערך בחו\"ל", "מסחר בניירות ערך זרים", "ניירות ערך זרים"],
    "securities_custody_il":      ["דמי ניהול פיקדון ניירות ערך הנסחרים בארץ", "דמי ניהול חשבון ניירות ערך", "דמי משמרת"],
    "securities_custody_foreign": ["דמי ניהול פיקדון ניירות ערך הנסחרים בחוץ לארץ", "ניירות ערך נסחרים בחו\"ל", "ניירות ערך הנסחרים בחו\"ל", "דמי ניהול ני\"ע חו\"ל"],
    "securities_custody_unlisted":["ניירות ערך שאינם נסחרים בבורסה"],
    "securities_transfer":        ["העברת ניירות ערך לחשבון אותו לקוח"],
    "securities_conversion":      ["המרת איגרות חוב", "מימוש אופציות", "המרת ניירות ערך דואליים"],
    "securities_issuance_order":  ["טיפול בהזמנה של ניירות ערך בהנפקה"],
    "trust_fund_distribution":    ["עמלת הפצה", "יחידת השתתפות בקרן נאמנות"],
    "securities_lending":         ["השאלת ניירות ערך"],
    "custodian_fee":              ["קסטודיאן"],

    # חלק 5
    "fx_conversion":              ["עמלת חליפין", "המרת מטבע", "פער המרה"],
    "fx_cash_deposit_withdraw":   ["הפקדת מזומן לחשבון מטבע חוץ", "משיכת מזומן מחשבון מטבע חוץ"],
    "fx_cash_exchange":           ["החלפת מזומן", "שטרות בלא שערים", "שטרות ישנים"],
    "fx_check_collection":        ["גביית שיקים במטבע חוץ", "גביה שיקים במטבע חוץ"],
    "fx_check_deposit_redeem":    ["הפקדת שיק במט\"ח", "פדיון שיק במט\"ח", "המחאות נוסעים"],
    "fx_travelers_check_sale":    ["מכירת המחאות נוסעים"],
    "fx_bank_check":              ["שיק בנקאי במט\"ח"],
    "fx_check_handling":          ["שיק משוך על חשבון מטבע חוץ"],
    "fx_transfer_abroad":         ["העברת מטבע חוץ לחוץ לארץ", "העברת מט\"ח לחו\"ל"],
    "fx_transfer_local":          ["העברת מטבע חוץ בארץ", "העברת מט\"ח בארץ"],
    "fx_value_days":              ["ימי ערך"],
    "fx_auto_overdraft_cover":    ["כיסוי אוטומטי של יתרת חובה בחשבון מטבע חוץ"],

    # חלק 6
    "debit_card_fee":             ["דמי כרטיס", "דמי כרטיס חיוב", "דמי כרטיס אשראי"],
    "card_topup_fee":             ["דמי טעינה", "עמלת טעינה"],
    "card_deferred_payment":      ["תשלום נדחה"],
    "card_charge_date_change":    ["שינוי מועד חיוב"],
    "card_dispute_unjust":        ["טיפול בהכחשה לא מוצדקת"],
    "card_early_repayment":       ["פירעון מוקדם של עסקאות", "פירעון מיידי של עסקאות"],
    "card_replacement_regular":   ["הנפקת כרטיס חליפי - רגילה", "כרטיס חליפי רגיל"],
    "card_replacement_express":   ["הנפקת כרטיס חליפי - מיידית", "כרטיס חליפי מיידי"],
    "card_fx_transactions_usd":   ["עסקאות בדולר או באירו"],
    "card_fx_transactions_other": ["עסקאות במטבע אחר"],
    "card_atm_fx_usd":            ["משיכת מזומן בדולר או באירו ממכשיר אוטומטי"],
    "card_atm_fx_other":          ["משיכת מזומן במטבע אחר ממכשיר אוטומטי"],
    "card_teller_fx_usd":         ["משיכת מזומן בדולר או באירו בדלפק"],
    "card_teller_fx_other":       ["משיכת מזומן במטבע אחר בדלפק"],
    "card_fx_same_currency":      ["משיכת מזומן במטבע חוץ מחשבון המנוהל באותו מטבע"],
    "card_fx_from_changer":       ["רכישת מטבע חוץ מחלפן"],

    # חלקים 7-15
    "trade_finance":              ["סחר חוץ"],
    "futures_transactions":       ["עסקאות עתידיות", "עסקאות בין מטבעיות", "בין-מטבעיות"],
    "post_holding":               ["שמירת דואר בסניף"],
    "safe_deposit_box":           ["שכירת כספות", "כספת"],
    "notes_handling":             ["טיפול בשטרות"],
    "estate_handling":            ["טיפול בירושות", "עיזבונות"],
    "foreign_atm_other_card":     ["מכשיר מרוחק", "כרטיס שלא הונפק"],
    "rights_assignment":          ["המחאת זכות"],
    "pension_advisory":           ["ייעוץ פנסיוני"],
    "prepaid_card_atm_withdrawal":["כרטיס נטען שלא מקושר"],
    "foreign_card_atm_withdrawal":["כרטיס חיוב אשר הונפק בחו\"ל"],

    "diamonds_services":          ["יהלומים"],

    "third_registration_fees":    ["אגרות רישום"],
    "third_appraiser":            ["הערכת שמאי", "שכר שמאי"],
    "third_emi_insurance":        ["EMI", "ביטוח הלוואה לדיור"],
    "third_notary_power":         ["ייפוי כוח נוטריוני", "אישור נוטריוני", "חתימה נוטריונית"],
    "third_companies_registrar":  ["רשם החברות"],
    "third_land_registrar":       ["רשם המקרקעין"],
    "third_returned_charge_bank": ["החזר שיק לטובת הבנק", "החזרת הרשאה לטובת הבנק"],
    "third_correspondent_bank":   ["בנק קורספונדנט", "קורספונדנט"],
    "third_broker_abroad":        ["ברוקר בחוץ לארץ", "ברוקר בחו\"ל"],
    "third_safe_insurance":       ["ביטוח כספת"],
    "third_abroad_mail":          ["דואר לחוץ לארץ", "משלוח כרטיס חליפי לחוץ לארץ"],
    "third_registered_mail":      ["דואר רשום"],
    "third_card_reader_use":      ["מכשירים לקריאת כרטיסי חיוב"],
    "third_fx_atm_abroad_teller": ["משיכת מזומן במטבע חוץ בחוץ לארץ בדלפק"],

    "clearing_active_biz_mgmt":   ["דמי ניהול בית עסק", "דמי ניהול חשבון סליקה"],
    "clearing_ecommerce_signup":  ["דמי הצטרפות של בית עסק אלקטרוני", "בית עסק אלקטרוני"],
    "clearing_verify_insure":     ["שירותי אימות פרטים", "ביטוח עסקה"],
    "clearing_cancel_transaction":["ביטול עסקה"],
    "clearing_chargeback":        ["החזר חיוב", "Charge Back"],
    "clearing_manual_voucher":    ["עיבוד שובר ידני"],
    "clearing_fee":               ["עמלת סליקה"],

    "discount_services_biz":      ["שירותי ניכיון לבתי עסק"],

    "payment_app_receive":        ["קבלת תשלום", "אפליקציית תשלום"],
    "payment_app_send":           ["הוראת תשלום באפליקציה", "תשלום באפליקציה", "תשלומים באפליקציה"],
    "payment_app_subscription":   ["דמי מנוי לשירות"],

    "financial_aggregator":       ["ריכוז מידע פיננסי", "ריכוז וניתוח מידע"],
}
