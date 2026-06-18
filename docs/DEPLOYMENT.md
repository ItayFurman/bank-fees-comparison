# פריסת המערכת לאינטרנט

מדריך זה מציג 3 אפשרויות חינמיות / זולות לפרוס את המערכת לאינטרנט.

---

## 🚀 אפשרות 1: Streamlit Community Cloud (חינם, הכי קל)

**יתרונות:** חינם, פריסה ב-3 דקות, HTTPS אוטומטי, עדכון אוטומטי כשמעלים ל-GitHub.
**מגבלות:** ה-app חייב להיות פתוח (לא פרטי) בריפוזיטורי GitHub. שעות "שינה" אחרי חוסר פעילות.

### שלב 1 — העלה ל-GitHub
1. צור חשבון ב-https://github.com (אם אין).
2. צור ריפוזיטורי חדש בשם `bank-fees-comparison`.
3. ב-PowerShell בתיקיית הפרויקט:
   ```powershell
   git init
   git add app.py download_pricelists.py qa_check.py requirements.txt
   git add src/ docs/ .streamlit/ .gitignore
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/USERNAME/bank-fees-comparison.git
   git push -u origin main
   ```
   (החלף `USERNAME` ב-username שלך)

### שלב 2 — פרוס ב-Streamlit Cloud
1. היכנס ל-https://share.streamlit.io עם חשבון GitHub.
2. לחץ **New app**.
3. בחר את הריפוזיטורי, branch `main`, ו-`app.py`.
4. לחץ **Deploy**.
5. תוך ~2 דקות יהיה לך URL כמו `https://bank-fees-comparison.streamlit.app`.

### שלב 3 — הוספת סוד למפתח API (אופציונלי)
אם תרצה את הסוכן LLM הפעיל:
1. בדף ה-app ב-Streamlit Cloud → ⚙️ **Settings** → **Secrets**.
2. הוסף:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
3. שמור — ה-app יקרא מחדש אוטומטית.

---

## 🌐 אפשרות 2: Hugging Face Spaces (חינם)

**יתרונות:** חינם, תומך ב-Streamlit ישירות, ללא הגבלת שעות שינה.
**מגבלות:** דורש העלאת קבצי PDF גם כן ל-Space.

1. https://huggingface.co/spaces → **Create new Space**.
2. בחר **Streamlit** כ-SDK.
3. העלה את אותם קבצים שב-Streamlit Cloud.
4. ה-URL: `https://huggingface.co/spaces/USERNAME/bank-fees-comparison`.

---

## ☁️ אפשרות 3: Render.com (חינם עם הגבלות)

**יתרונות:** PostgreSQL חינמי, custom domain, יותר זיכרון.
**מגבלות:** Free tier "ישן" אחרי 15 דק' חוסר פעילות.

1. https://render.com → **New +** → **Web Service**.
2. חבר את ריפוזיטורי ה-GitHub.
3. ב-Build Command: `pip install -r requirements.txt`
4. ב-Start Command:
   ```
   streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```
5. בחר **Free** plan ופרוס.

---

## 🔐 הערות אבטחה ופרטיות

**חשוב:** התעריפונים שהורדת והנתונים שחילצת כוללים מידע על תעריפי בנקים בפועל.
- אם הריפוזיטורי שלך **פומבי**: ה-`.gitignore` כבר מסנן את `pdfs/`, `output/`, `agent_memory/` — לא יועלו ל-GitHub.
- אם תרצה לחשוף ל-app את הנתונים בענן: העלה אותם דרך הסיידבר (file uploader) ולא ב-Git.
- **לעולם אל** תעלה את ה-`ANTHROPIC_API_KEY` ישירות לקוד או ל-GitHub — תמיד דרך Secrets של הפלטפורמה.

---

## ✅ בדיקת מוכנות לפני פריסה

הרץ אישית לפני שאתה דוחף ל-GitHub:

```powershell
cd "C:\claude code course\מערכת להשוואת תעריפונים"
.\.venv\Scripts\python.exe qa_check.py
```

זה מאתר ערכים חשודים שאולי תרצה לתקן (או לפחות לדעת עליהם) לפני שמשתמשים אחרים רואים.

---

## 🌍 שיתוף עם משתמשים אחרים

לאחר הפריסה — כל אחד עם ה-URL יכול:
1. להעלות PDFים של תעריפונים דרך הסיידבר.
2. לראות השוואות.
3. להריץ את הסוכן.
4. **כל משתמש מקבל סשן נפרד** — הנתונים לא נשמרים בין משתמשים (ב-Streamlit Cloud).

אם תרצה שמשתמשים יחלקו ממצאי הסוכן בין יש"א — נדרש backend עם מסד נתונים (Postgres ב-Render / Supabase חינמי). תגיד לי ואטפל בזה.
