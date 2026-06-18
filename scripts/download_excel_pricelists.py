"""
הורדת תעריפוני בנקים בפורמט Excel מהאתרים הרשמיים.
לפי כללי הבנקאות (שירות ללקוח) (עמלות), כל בנק חייב לפרסם תעריפון
גם בפורמט Excel — קל יותר לקריאה מאוטומציה.

Run:  python scripts/download_excel_pricelists.py
"""
from __future__ import annotations
import sys
import urllib.request
import ssl
from pathlib import Path

EXCEL_DIR = Path(__file__).resolve().parent.parent / "excel"
EXCEL_DIR.mkdir(exist_ok=True)

# שם קובץ -> (URL, תיאור)
SOURCES: dict[str, tuple[str, str]] = {
    "hapoalim.xls":     (
        "https://www.bankhapoalim.co.il/sites/default/files/media/PDFS/Taarifon/"
        "%D7%AA%D7%A2%D7%A8%D7%99%D7%A4%D7%95%D7%9F%20%D7%9E%D7%9C%D7%90%20"
        "%D7%A2%D7%A1%D7%A7%20%D7%A7%D7%98%D7%9F.xls",
        "הפועלים — תעריפון מלא עסק קטן",
    ),
    "discount.xlsx":    (
        "https://www.discountbank.co.il/DB/sites/marketing.discountbank.co.il/"
        "files/CMS%20media/Personal_Banking/Documents/tariff/private_SMB/"
        "Tarifon_Private_bound_small_290522.xlsx",
        "דיסקונט — תעריפון מאוגד",
    ),
    "jerusalem.xls":    (
        "https://www.bankjerusalem.co.il/media/2423/"
        "%D7%AA%D7%A2%D7%A8%D7%99%D7%A4%D7%95%D7%9F-%D7%99%D7%97%D7%99%D7%93-"
        "%D7%A2%D7%A1%D7%A7-%D7%A7%D7%98%D7%9F-%D7%9E%D7%9C%D7%90.xls",
        "ירושלים — תעריפון מלא יחיד/עסק קטן",
    ),
    "yahav.xlsx":       (
        "https://bank-yahav.co.il/media/020jnu0x/2-2025_taarifon_male.xlsx",
        "יהב — תעריפון יחיד/עסק קטן 2-2025",
    ),
    "mizrahi.xls":      (
        "https://www.mizrahi-tefahot.co.il/media/smallbusinessMeugad.xls",
        "מזרחי טפחות — תעריפון מאוגד יחיד",
    ),
    "mercantile.xlsx":  (
        "https://www.mercantile.co.il/media/jjjeokcr/taarifon_private_full_1126.xlsx",
        "מרכנתיל — תעריפון מלא יחיד/עסק קטן",
    ),
    "leumi.xls":        (
        "https://www.bankleumi.co.il/static-files/Commissions_Leumi/"
        "AmlotYechidimL.xls",
        "לאומי — תעריפון העמלות המלא ליחידים/עסקים קטנים",
    ),
}

# בנקים שלא חושפים Excel ישירות — נדרשת הורדה ידנית מהאתר
MANUAL_DOWNLOAD: dict[str, str] = {
    "max.xls":        "https://www.max.co.il/cards/pages/commissions  "
                       "(מקס היא חברת כרטיסי אשראי — מפרסמת תעריפון כ-PDF בלבד, אין Excel)",
    "one_zero.xls":   "https://www.onezerobank.com/company/information/2250  "
                       "(האתר מאחורי Cloudflare ומחזיר 403 לכל בוט — דרושה הורדה ידנית מהדפדפן)",
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/vnd.ms-excel,application/vnd.openxmlformats*,*/*",
}


def download(url: str, dest: Path) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = resp.read()
        if len(data) < 1024:
            return False, f"קובץ קטן מדי ({len(data)} bytes)"
        # ודא ש-magic bytes של xlsx ('PK') או xls ('\xd0\xcf')
        is_xlsx = data[:2] == b"PK"
        is_xls  = data[:2] == b"\xd0\xcf"
        if not (is_xlsx or is_xls):
            return False, "לא קובץ Excel תקין"
        dest.write_bytes(data)
        return True, f"{len(data)//1024} KB"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    print(f"מוריד אקסלים לתיקייה: {EXCEL_DIR}\n")
    ok, fail = 0, 0
    for filename, (url, label) in SOURCES.items():
        dest = EXCEL_DIR / filename
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
        print("\n--- בנקים שדורשים הורדה ידנית ---")
        print("פתח את ה-URL, הורד את התעריפון בפורמט Excel, ושמור ב-excel/")
        for fname, page in MANUAL_DOWNLOAD.items():
            print(f"  • {fname:18s} <- {page}")


if __name__ == "__main__":
    sys.exit(main())
