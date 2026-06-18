"""
Probe candidate Excel-pricelist URLs for banks that only expose PDF
(Leumi, One Zero, Max). For each candidate we report HTTP status,
content-type, size, and Excel magic bytes -- without saving garbage.

Run:  python scripts/probe_excel_urls.py
ASCII-only output so it never crashes the Windows console.
"""
from __future__ import annotations
import sys
import ssl
import urllib.request
import urllib.error
from pathlib import Path

EXCEL_DIR = Path(__file__).resolve().parent.parent / "excel"
EXCEL_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.ms-excel,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/octet-stream,*/*"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

# (label, save_stem, [candidate urls]) -- extension chosen from magic bytes
CANDIDATES: list[tuple[str, str, list[str]]] = [
    (
        "Leumi (full, individuals/small-biz)",
        "leumi",
        [
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidimL.xlsx",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidimL.xls",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidim.xlsx",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidim.xls",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidimL.csv",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/Amlot_Yechidim.xlsx",
            "https://www.bankleumi.co.il/static-files/Commissions_Leumi/AmlotYechidimFull.xlsx",
        ],
    ),
    (
        "One Zero (full list of charges)",
        "one_zero",
        [
            "https://www.onezerobank.com/warehouse/userUploadFiles/Image/ONE%20ZERO%20list%20of%20charges%20-%20Long.xlsx",
            "https://www.onezerobank.com/warehouse/userUploadFiles/Image/ONE%20ZERO%20list%20of%20charges%20-%20Long.xls",
            "https://www.onezerobank.com/warehouse/userUploadFiles/Image/ONE%20ZERO%20list%20of%20charges%20-%20Long.csv",
            "https://www.onezerobank.com/warehouse/userUploadFiles/Image/ONE%20ZERO%20list%20of%20charges%20Long%20Feb26%20announcement.xlsx",
            "https://www.onezerobank.com/warehouse/userUploadFiles/Image/ONE%20ZERO%20list%20of%20charges%20Long.xlsx",
        ],
    ),
    (
        "Max (general credit-card tariff)",
        "max",
        [
            "https://onlinelcapi.max.co.il/SharedMedia/3402/tariff_general.xlsx",
            "https://onlinelcapi.max.co.il/SharedMedia/3402/tariff_general.xls",
            "https://www.max.co.il/cards/pages/commissions.xlsx",
        ],
    ),
]


def probe(url: str) -> tuple[str, bytes]:
    """Return (status_line, first_bytes). Never raises."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            ctype = resp.headers.get("Content-Type", "?")
            clen = resp.headers.get("Content-Length", "?")
            data = resp.read()
        head = data[:8]
        is_xlsx = head[:2] == b"PK"
        is_xls = head[:2] == b"\xd0\xcf"
        kind = "XLSX" if is_xlsx else "XLS" if is_xls else "not-excel"
        status = (
            f"HTTP 200 | {kind} | type={ctype} | "
            f"clen={clen} | got={len(data)}B"
        )
        return status, (data if (is_xlsx or is_xls) else b"")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.reason}", b""
    except Exception as e:
        return f"ERR {type(e).__name__}: {e}", b""


def main() -> int:
    print(f"Excel dir: {EXCEL_DIR}\n")
    saved = 0
    for label, save_stem, urls in CANDIDATES:
        print(f"== {label} ==")
        hit = False
        for url in urls:
            status, data = probe(url)
            tail = url.rsplit("/", 1)[-1]
            print(f"   [{status}]  {tail}")
            if data and not hit:
                # בחר סיומת לפי magic bytes: PK=xlsx, \xd0\xcf=xls
                ext = ".xlsx" if data[:2] == b"PK" else ".xls"
                save_as = f"{save_stem}{ext}"
                dest = EXCEL_DIR / save_as
                dest.write_bytes(data)
                print(f"   --> SAVED {len(data)//1024} KB to excel/{save_as}")
                saved += 1
                hit = True
        if not hit:
            print("   (no Excel found at any candidate)")
        print()
    print(f"Done. Saved {saved} new Excel file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
