# 🚀 העלאת המערכת לאינטרנט — מדריך מהיר

המערכת כבר מוכנה לפריסה. **רוב העבודה אוטומטית.** רק 3 דברים שאתה חייב לעשות בעצמך כי הם דורשים חשבונות אישיים.

---

## ⏱️ ציר זמן: 15 דקות מ-0 לפריסה

### ☑️ שלב 1: צור חשבון GitHub (5 דקות) — **רק אתה יכול**

1. https://github.com/signup
2. בחר username — זה יהיה חלק מהקישור הציבורי שלך
3. אשר אימייל

### ☑️ שלב 2: צור Repository חדש (1 דקה) — **רק אתה יכול**

1. https://github.com/new
2. **Repository name:** `bank-fees-comparison`
3. **חייב להיות Public** (כדי שיהיה חינמי ב-Streamlit Cloud)
4. **אל תסמן** "Add README", "Add gitignore", "Add license"
5. לחץ **Create repository**

### ☑️ שלב 3: יצירת Personal Access Token (1 דקה) — **רק אתה יכול**

GitHub כבר לא מקבל סיסמה רגילה ל-push. צריך token:

1. https://github.com/settings/tokens/new
2. **Note:** `streamlit deploy`
3. **Expiration:** 90 days
4. **Scope:** סמן `repo` בלבד
5. לחץ **Generate token**
6. **העתק את ה-token** (הוא יוצג רק פעם אחת!) — שמור אותו זמנית

### 🚀 שלב 4: הרץ את הסקריפט — **כל השאר אוטומטי**

לחץ פעמיים על **`DEPLOY_TO_CLOUD.bat`**

הסקריפט:
- ✅ יוודא ש-git מותקן
- ✅ יאתחל את ה-repository המקומי
- ✅ ישאל את ה-username שלך ב-GitHub
- ✅ יוסיף את ה-remote
- ✅ יבצע commit ו-push

**כשמתבקש סיסמה — הדבק את ה-Token שיצרת בשלב 3.**

### ✅ שלב 5: פרוס ב-Streamlit Cloud (2 דקות)

1. https://share.streamlit.io
2. Sign in with GitHub
3. **New app**
4. Repository: `your-username/bank-fees-comparison`
5. Branch: `main`
6. Main file path: `app.py`
7. **Deploy**

תוך 2 דקות תקבל **URL ציבורי** כמו:
```
https://bank-fees-comparison.streamlit.app
```

**זה הקישור שתשתף עם כל מי שתרצה.**

---

## 🤖 הפעלת סוכן AI אמיתי (אופציונלי, $5 קרדיט חינם)

ברירת המחדל — הסוכן עובד עם **תבניות חכמות** (לא AI אמיתי).
להפעלת Claude API:

### א. קבל מפתח API
1. https://console.anthropic.com
2. הירשם (תקבל $5 קרדיט חינם)
3. **API Keys → Create Key**
4. העתק (מתחיל ב-`sk-ant-...`)

### ב. הוסף לסודות של Streamlit
1. ב-app שלך ב-Streamlit Cloud → **⚙️ Settings**
2. **Secrets** → הדבק:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
3. **Save** — האפליקציה תיטען מחדש אוטומטית
4. בטאב הסוכן תראה **🟢 LLM פעיל** במקום 🟡 תבניות

עלות שימוש: ~$0.003 לשיחה. $5 = ~1,500 שיחות.

---

## 🔐 שיקולי פרטיות

הקבצים הבאים **לא** יעלו ל-GitHub (מסונן ב-`.gitignore`):
- `pdfs/*.pdf` — תעריפוני בנקים שהורדת
- `output/` — נתונים מנורמלים
- `agent_memory/` — שיחות הסוכן ו-verdicts
- `regulations/` — מסמכים רגולטוריים מקומיים

**מה כן יעלה:** הקוד, הסכמה, הוראות, צבעי הבנקים, ו-bare bones.

**משתמשים אחרים בענן:** כל אחד נכנס ל-URL → רואה ממשק ריק → יכול להעלות PDFים משלו → רואה ניתוח. **אין שיתוף נתונים בין משתמשים** (ב-Streamlit Cloud — הכל בזיכרון, נמחק כשהפעלה נסגרת).

אם תרצה שיתוף נתונים בין משתמשים (למשל צוות פיקוח שעובד יחד) — צריך להוסיף מסד נתונים (Postgres ב-Supabase, חינמי). תגיד לי ואטפל בזה.

---

## 🆘 פתרון בעיות נפוצות

### "git push failed - authentication"
- ודא שאתה משתמש ב-**Personal Access Token** במקום סיסמה
- ה-token חייב כולל scope `repo`

### "Repository already exists"
- אם יצרת בעבר repo בשם הזה, מחק אותו או בחר שם אחר ב-`DEPLOY_TO_CLOUD.bat`

### "Streamlit app failed to load"
- בדוק את ה-Logs ב-Streamlit Cloud
- ודא ש-`requirements.txt` כולל את כל החבילות
- ודא ש-`app.py` בשורש ה-repo

### "Hebrew text appears reversed"
- זה לא יקרה ב-Streamlit Cloud — מקודד נכון אוטומטית
