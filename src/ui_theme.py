"""
עיצוב RTL + צבעי מותג לבנקים. מספק:
  • inject_rtl_css() – CSS גלובלי שמהפך את האפליקציה לימין-לשמאל.
  • bank_color_css() – צביעת עמודות בנקים בטבלאות לפי הצבע שלהם.
  • style_dataframe_with_banks() – Pandas Styler עם צבעי בנקים.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd

from .bank_profiles import PROFILES, PROFILES_BY_ID


RTL_CSS = """
<style>
/* === כל האפליקציה ימין-לשמאל === */
html, body, .stApp, [class*="css"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stSidebar"] {
    direction: rtl !important;
    text-align: right !important;
}

/* כותרות וטקסט */
h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stCaption,
[data-testid="stMarkdownContainer"] {
    direction: rtl !important;
    text-align: right !important;
    font-family: -apple-system, "Segoe UI", "Arial Hebrew", Arial, sans-serif !important;
}

/* טאבים - מימין */
.stTabs [data-baseweb="tab-list"] {
    direction: rtl !important;
    justify-content: flex-end !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}

/* כפתורים */
.stButton button, [data-testid="stDownloadButton"] button {
    direction: rtl !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}

/* טבלאות - תוכן מימין */
[data-testid="stDataFrame"] {
    direction: rtl !important;
}
[data-testid="stDataFrame"] table {
    direction: rtl !important;
}
[data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td {
    text-align: right !important;
    direction: rtl !important;
}

/* input ו-textarea */
.stTextInput input, .stTextArea textarea, .stSelectbox select,
.stMultiSelect div[data-baseweb="select"], .stChatInput textarea {
    direction: rtl !important;
    text-align: right !important;
}

/* multiselect chips - מימין */
.stMultiSelect [data-baseweb="tag"] {
    direction: rtl !important;
}

/* expander - חץ בצד שמאל */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    direction: rtl !important;
    text-align: right !important;
}

/* chat messages - מימין */
[data-testid="stChatMessage"] {
    direction: rtl !important;
}

/* metrics - מימין */
[data-testid="stMetric"], [data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {
    direction: rtl !important;
    text-align: right !important;
}

/* alerts (info/warning/success/error) */
[data-testid="stAlert"], .stAlert {
    direction: rtl !important;
    text-align: right !important;
}

/* === שיפורי עיצוב === */
.stApp {
    background: linear-gradient(135deg, #fafafa 0%, #f0f4f8 100%);
}

/* כותרת ראשית */
h1 {
    color: #1a1f36 !important;
    border-bottom: 3px solid #ffc107 !important;
    padding-bottom: 10px !important;
    margin-bottom: 20px !important;
}

/* טאבים - הדגשה ברורה של הנבחר */
.stTabs [aria-selected="true"] {
    background-color: #1a4378 !important;
    color: white !important;
    border-radius: 8px 8px 0 0 !important;
}

/* כפתור primary */
.stButton button[kind="primary"] {
    background-color: #1a4378 !important;
    color: white !important;
    border: none !important;
}
.stButton button[kind="primary"]:hover {
    background-color: #0f2f5f !important;
    transform: translateY(-1px);
}

/* metrics - כרטיסיות צבעוניות */
[data-testid="stMetric"] {
    background: white !important;
    padding: 12px !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
    border-right: 4px solid #1a4378 !important;
}

/* expander */
.streamlit-expanderHeader {
    background-color: #f8fafc !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

/* dataframe header - כהה ובולט */
[data-testid="stDataFrame"] thead tr {
    background-color: #1a1f36 !important;
}
[data-testid="stDataFrame"] thead th {
    color: #ffffff !important;
    font-weight: 700 !important;
}

/* שורות לסירוגין */
[data-testid="stDataFrame"] tbody tr:nth-child(even) {
    background-color: #f8fafc !important;
}

/* container עם border */
[data-testid="stVerticalBlock"] > [style*="border"] {
    border-radius: 12px !important;
}
</style>
"""


def inject_rtl_css():
    """מזריק CSS גלובלי לעיצוב ימין-לשמאל."""
    st.markdown(RTL_CSS, unsafe_allow_html=True)
    st.markdown(_build_bank_palette_css(), unsafe_allow_html=True)


def _build_bank_palette_css() -> str:
    """יוצר CSS דינמי עם צבעי המותג של כל בנק."""
    rules = ["<style>"]
    for p in PROFILES:
        # class לפי bank_id (לשימוש בכותרות עמודות מותאמות)
        rules.append(
            f".bank-color-{p.bank_id} {{ "
            f"background-color: {p.brand_color} !important; "
            f"color: {p.text_color} !important; "
            f"padding: 6px 10px; border-radius: 6px; font-weight: 600; "
            f"display: inline-block; }}"
        )
    rules.append("</style>")
    return "\n".join(rules)


def bank_color_badge(bank_id: str) -> str:
    """מחזיר HTML של תווית עם צבע המותג של הבנק."""
    p = PROFILES_BY_ID.get(bank_id)
    if not p:
        return bank_id
    return (
        f'<span class="bank-color-{bank_id}" '
        f'style="background-color:{p.brand_color};color:{p.text_color};'
        f'padding:4px 10px;border-radius:6px;font-weight:600;'
        f'display:inline-block;">{p.display_name}</span>'
    )


def bank_color_for_name(display_name: str) -> str | None:
    """מאתר צבע מותג לפי שם תצוגה (להתאמה לטבלת השוואה)."""
    for p in PROFILES:
        if p.display_name == display_name:
            return p.brand_color
    return None


def style_comparison_dataframe(df: pd.DataFrame, bank_cols: list[str]):
    """
    מעצב Pandas DataFrame בטבלת השוואה — צובע את כותרות הבנקים בצבעי המותג
    ומחיל עיצוב RTL לכל התאים.
    """
    bank_color_map = {bc: bank_color_for_name(bc) for bc in bank_cols}

    def _header_style(col_name):
        color = bank_color_map.get(col_name)
        if color:
            return f"background-color: {color}; color: white; " \
                   f"text-align: right; padding: 8px; font-weight: 700;"
        return "text-align: right; padding: 8px; font-weight: 700;"

    styler = df.style.set_table_styles([
        {"selector": f"th.col_heading.col{i}",
         "props": _header_style(col)}
        for i, col in enumerate(df.columns)
    ])

    # יישור כללי לטבלה - מימין לשמאל
    styler = styler.set_table_attributes('dir="rtl" style="text-align:right;"')
    styler = styler.set_properties(**{
        "text-align": "right",
        "direction": "rtl",
        "white-space": "pre-wrap",
        "vertical-align": "top",
        "padding": "8px",
    })

    # רקע עדין לעמודות בנק
    for bank_col, color in bank_color_map.items():
        if color and bank_col in df.columns:
            # רקע עדין (10% מהצבע) לעמודה
            styler = styler.set_properties(
                subset=[bank_col],
                **{"background-color": f"{color}14",
                   "border-right": f"3px solid {color}"}
            )

    return styler


def render_bank_legend():
    """מציג מקרא צבעוני של כל הבנקים."""
    html = '<div style="display:flex;flex-wrap:wrap;gap:8px;direction:rtl;' \
           'padding:10px 0;">'
    for p in PROFILES:
        html += (
            f'<span style="background-color:{p.brand_color};color:{p.text_color};'
            f'padding:6px 12px;border-radius:20px;font-weight:600;'
            f'font-size:0.85rem;">{p.display_name}</span>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
