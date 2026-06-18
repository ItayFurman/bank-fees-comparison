"""
PDF extraction engines — מספר מנועים עם fallback אוטומטי.

Strategy:
  1. pdfplumber (מהיר, טוב לטבלאות, נכשל ב-CID fonts)
  2. pymupdf (fitz) (טוב לפענוח Unicode, פחות טוב לטבלאות)
  3. cp1255 post-decode (לקבצים שמחזירים תווי Latin-1 שצריך לתרגם לעברית)

המנוע הראשי בוחר את הטוב ביותר אוטומטית לפי "ציון איכות" של הטקסט.
"""
from .engine import extract_with_best_engine, evaluate_text_quality

__all__ = ["extract_with_best_engine", "evaluate_text_quality"]
