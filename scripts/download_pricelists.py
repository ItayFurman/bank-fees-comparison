"""
הורדת תעריפוני בנקים רשמיים מהאתרים הרשמיים שלהם.
לחץ פעמיים על 'הורד תעריפונים.bat' או הרץ:  python download_pricelists.py
"""
from __future__ import annotations
import sys
import urllib.request
import ssl
from pathlib import Path

PDF_DIR = Path(__file__).resolve().parent.parent / "pdfs"
PDF_DIR.mkdir(exist_ok=True)

# שם קובץ -> (URL רשמי לתעריפון המלא, תיאור גרסה)
# המקור: עמודי "תעריפון מלא ליחיד/עסק קטן" באתרי הבנקים הרשמיים, מעודכן 2025.
SOURCES: dict[str, tuple[str, str]] = {
    "leumi.pdf":     ("https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidimL.pdf",
                      "תעריפון מלא יחיד/עסק קטן"),
    "hapoalim.pdf":  ("https://www.bankhapoalim.co.il/sites/default/files/media/PDFS/Taarifon/small_single_3526.pdf",
                      "תעריפון מלא יחיד/עסק קטן (נובמבר 2025)"),
    "discount.pdf":  ("https://www.discountbank.co.il/media/j25ppj4p/tarif_small_buisness_15426.pdf",
                      "תעריפון מאוגד מלא (פברואר 2025)"),
    "mizrahi.pdf":   ("https://www.mizrahi-tefahot.co.il/media/smallbusinessMeugad.pdf",
                      "תעריפון מלא מאוגד יחיד/עסק קטן"),
    "yahav.pdf":     ("https://bank-yahav.co.il/media/fhukyxkr/2-2025_taarifon_male.pdf",
                      "תעריפון יחיד/עסק קטן (פברואר 2025)"),
    "jerusalem.pdf": ("https://www.bankjerusalem.co.il/media/3961/%D7%AA%D7%A2%D7%A8%D7%99%D7%A4%D7%95%D7%9F-%D7%99%D7%97%D7%99%D7%93-%D7%A2%D7%A1%D7%A7-%D7%A7%D7%98%D7%9F-%D7%9E%D7%9C%D7%90.pdf",
                      "תעריפון מלא יחיד/עסק קטן"),
    # massad ו-one_zero חוסמים הורדה אוטומטית של הגרסה המעודכנת —
    # הקבצים העדכניים (10052026 ו-Feb26) הוטענו ידנית ע"י המשתמש.
    "max.pdf":       ("https://onlinelcapi.max.co.il/SharedMedia/17263/%D7%AA%D7%A2%D7%A8%D7%99%D7%A4%D7%95%D7%9F-%D7%A2%D7%9E%D7%9C%D7%95%D7%AA-%D7%9B%D7%9C%D7%9C%D7%99-32024-30-12-117-%D7%9E%D7%95%D7%A0%D7%92%D7%A9.pdf",
                      "תעריפון עמלות כללי (מארס 2024)"),
    "mercantile.pdf":("https://www.mercantile.co.il/media/jjjeokcr/taarifon_private_full_1126.pdf",
                      "תעריפון מלא יחיד/עסק קטן"),
    "beinleumi.pdf": ("https://www.fibi.co.il/media/5byfq3ai/%D7%AA%D7%A2%D7%A8%D7%99%D7%A4%D7%95%D7%9F-%D7%91%D7%99%D7%A0%D7%9C%D7%90%D7%95%D7%9E%D7%99-%D7%99%D7%97%D7%99%D7%93%D7%99%D7%9D-02122024.pdf",
                      "תעריפון בינלאומי ליחידים ועסקים קטנים (דצמ' 2024)"),
}

# בנקים שדורשים הורדה ידנית (אתר חוסם בוטים) — הוטענו ידנית ע"י המשתמש.
MANUAL_DOWNLOAD: dict[str, str] = {}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}

def download(url: str, dest: Path) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = resp.read()
        if len(data) < 1024:
            return False, f"קובץ קטן מדי ({len(data)} bytes) — כנראה דף שגיאה"
        if not (data[:5] == b"%PDF-" or b"%PDF-" in data[:1024]):
            return False, "לא קובץ PDF (אולי האתר מחזיר HTML)"
        dest.write_bytes(data)
        return True, f"{len(data)//1024} KB"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    print(f"מוריד תעריפונים לתיקייה: {PDF_DIR}\n")
    ok, fail = 0, 0
    for filename, (url, label) in SOURCES.items():
        dest = PDF_DIR / filename
        print(f"  • {filename:18s} [{label}]")
        print(f"      ... ", end="", flush=True)
        success, info = download(url, dest)
        if success:
            print(f"OK  ({info})")
            ok += 1
        else:
            print(f"נכשל — {info}")
            fail += 1

    print(f"\nסיכום: {ok} הצליחו, {fail} נכשלו.")
    if MANUAL_DOWNLOAD:
        print("\n--- הורדה ידנית נדרשת ---")
        print("הבנקים הבאים חוסמים הורדה אוטומטית. פתח את הקישור בדפדפן,")
        print("הורד את ה-PDF, ושמור בתיקיית pdfs/ עם השם המצוין:")
        for fname, page in MANUAL_DOWNLOAD.items():
            print(f"  • {fname:18s} <- {page}")


if __name__ == "__main__":
    sys.exit(main())
