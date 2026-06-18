"""
Streamlit GUI להשוואת תעריפוני בנקים — RTL, צבעי מותג, סוכן AI משופר.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import Counter

import pandas as pd
import streamlit as st

from src.extractor import extract_rows
from src.normalizer import normalize, to_jsonable, NormalizedFee, collect_unmatched
from src.bank_profiles import PROFILES, PROFILES_BY_ID, detect_bank
from src.ingest import ingest_all
from src.excel_extractor import extract_excel_rows
from src.comparator import (build_comparison, cheapest_per_fee,
                             get_bank_columns, build_deviation_report)
from src.schema import (CANONICAL_FEES, FEE_BY_KEY, PARTS_ORDER, PARTS_INDEX,
                         SUPPLEMENTS, APPENDICES)
from src.compliance_agent import (scan_compliance, save_findings, load_findings,
                                   update_verdict, RISK_CATEGORIES, ComplianceFinding,
                                   bank_risk_scores, top_findings, merge_with_history,
                                   bulk_update_verdict,
                                   build_cross_bank_comparison,
                                   get_comparison_for_finding)
from src.agent_chat import (AgentChat, ChatMessage, Conversation,
                             load_conversation, save_conversation)
from src.ui_theme import inject_rtl_css, bank_color_for_name, render_bank_legend
from src.security import (safe_filename, validate_pdf_bytes, esc,
                           truncate, log_security_event)

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "pdfs"
OUT_DIR = ROOT / "output"
PDF_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="השוואת תעריפוני בנקים",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────── עיצוב RTL וצבעי מותג ───────
inject_rtl_css()

st.title("📋 השוואת תעריפוני בנקים")
st.caption(
    "מערכת בקרת תאימות לפי **כללי הבנקאות (שירות ללקוח) (עמלות), התשס\"ח-2008** "
    "(נבו) ו**מכתב המפקח על הבנקים 25LM5593** (10.12.2025). | גרסה 1.1"
)


# ========== Sidebar ==========
with st.sidebar:
    st.header("📥 העלאת תעריפונים")
    uploaded = st.file_uploader(
        "קבצי PDF (אפשר מספר קבצים)",
        type=["pdf"], accept_multiple_files=True,
    )
    if uploaded:
        accepted, rejected = 0, []
        for uf in uploaded:
            # תיקון Path Traversal: סניטיזציה של שם הקובץ
            safe_name = safe_filename(uf.name)
            data = uf.getbuffer().tobytes()

            # ולידציית PDF magic-bytes נגד קבצים מזויפים
            ok, err = validate_pdf_bytes(data)
            if not ok:
                rejected.append(f"{uf.name}: {err}")
                log_security_event(
                    "rejected_upload",
                    f"name={uf.name!r} reason={err}",
                    severity="warning",
                )
                continue

            # שמירה לתיקייה — safe_name לא יכיל '..' או '/'
            target = PDF_DIR / safe_name
            # ודא שהיעד באמת בתוך PDF_DIR (defense in depth)
            try:
                target.resolve().relative_to(PDF_DIR.resolve())
            except ValueError:
                rejected.append(f"{uf.name}: שם קובץ לא תקין")
                log_security_event(
                    "path_traversal_attempt",
                    f"name={uf.name!r}",
                    severity="critical",
                )
                continue

            target.write_bytes(data)
            accepted += 1

        if accepted:
            st.success(f"✅ נשמרו {accepted} קבצים")
        if rejected:
            with st.expander(f"⚠ {len(rejected)} קבצים נדחו"):
                for r in rejected:
                    st.warning(r)

    st.divider()
    st.header("⚙️ חילוץ ונרמול")
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        st.info("טרם הועלו קבצים.")
    else:
        with st.expander(f"📂 {len(pdfs)} קבצים זמינים", expanded=False):
            for p in pdfs:
                prof = detect_bank(p.name)
                label = prof.display_name if prof else "❓ לא זוהה"
                short = p.name if len(p.name) < 32 else p.name[:29] + "…"
                color = prof.brand_color if prof else "#888"
                # XSS hardening: escape תוכן user-controlled
                st.markdown(
                    f'<div style="border-right:4px solid {esc(color)};padding:4px 8px;'
                    f'margin:2px 0;background:#fafafa;border-radius:4px;">'
                    f'<code style="font-size:0.75rem;">{esc(short)}</code><br>'
                    f'<span style="color:{esc(color)};font-weight:600;font-size:0.85rem;">'
                    f'{esc(label)}</span></div>',
                    unsafe_allow_html=True,
                )

        if st.button("🔄 הרץ חילוץ מלא (PDF + Excel)",
                       type="primary", width="stretch"):
            with st.spinner("מחלץ PDF + Excel ומשלב את התוצאות..."):
                results = ingest_all()
            st.success(f"✅ הושלם — {sum(r.matched_fees for r in results)} "
                        f"עמלות מזוהות ב-{len(results)} בנקים. רענן (F5).")

            # תצוגה מהירה של מקור הנתונים
            for r in results:
                if r.matched_fees == 0:
                    icon = "❌"
                elif r.source_summary == "PDF+Excel":
                    icon = "🟢"
                elif r.source_summary == "Excel בלבד":
                    icon = "🔵"
                else:
                    icon = "🟡"
                st.caption(
                    f"{icon} **{r.display_name}** ({r.source_summary}): "
                    f"{r.matched_fees} עמלות"
                )

    st.divider()
    st.header("📊 קבצי Excel")
    EXCEL_DIR = ROOT / "excel"
    excels = sorted(EXCEL_DIR.glob("*.xls*")) if EXCEL_DIR.exists() else []
    if excels:
        st.caption(f"{len(excels)} אקסלים זמינים (אם קיים — מועדף על PDF)")
        for e in excels:
            prof = detect_bank(e.name)
            label = prof.display_name if prof else "❓"
            color = prof.brand_color if prof else "#888"
            st.markdown(
                f'<div style="border-right:3px solid {esc(color)};padding:3px 8px;'
                f'margin:2px 0;background:#f0fdf4;border-radius:4px;font-size:0.8rem;">'
                f'📊 {esc(e.name[:30])} → <strong>{esc(label)}</strong></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("אין קבצי Excel. הרץ:\n`python scripts/download_excel_pricelists.py`")

    st.divider()
    st.header("🎨 צבעי הבנקים")
    render_bank_legend()


# ========== טעינת נתונים (עם caching לחיסכון בזיכרון) ==========
@st.cache_data(show_spinner=False)
def _load_bank_options(file_signatures: tuple) -> dict:
    """
    טעינת כל ה-JSON של הבנקים. cached לפי signature של הקבצים.
    file_signatures = ((name, mtime, size), ...) — משתנה רק כשהקבצים משתנים.
    """
    result = {}
    for f in OUT_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result[data["display_name"]] = data
        except Exception:
            pass
    return result


available = sorted(OUT_DIR.glob("*.json"))
if not available:
    st.warning("📭 אין קבצי JSON ב-output/. העלה PDFים בסיידבר והרץ חילוץ.")
    st.stop()

# signature לטריגור cache invalidation
file_sigs = tuple((f.name, f.stat().st_mtime, f.stat().st_size)
                    for f in available)
bank_options = _load_bank_options(file_sigs)

if not bank_options:
    st.stop()

# ========== בקרות גלובליות ==========
with st.container(border=True):
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        selected_names = st.multiselect(
            "🏦 בנקים להשוואה",
            options=list(bank_options.keys()),
            default=list(bank_options.keys()),
        )
    with c2:
        parts_selected = st.multiselect(
            "📑 חלקים בתעריפון",
            options=PARTS_ORDER,
            default=PARTS_ORDER,
        )
    with c3:
        only_regulated = st.checkbox("רק עמלות בפיקוח", value=False)
        hide_empty = st.checkbox("הסתר שורות ריקות", value=True)

if not selected_names:
    st.info("בחר לפחות בנק אחד.")
    st.stop()

by_bank: dict[str, dict[str, NormalizedFee]] = {}
for name in selected_names:
    data = bank_options[name]
    fees = {k: NormalizedFee(**v) for k, v in data["fees"].items()}
    by_bank[data["bank_id"]] = fees


# ========== Helper: רנדור HTML של טבלת השוואה ==========
def render_html_comparison_table(df: pd.DataFrame, bank_cols: list[str],
                                  meta_cols: list[str]) -> str:
    """
    בונה HTML עם טקסט מלא בכל תא + צבעי מותג בכותרות בנקים +
    text-wrap מלא + RTL.
    """
    # --- CSS לטבלה ---
    css = """
    <style>
    .comparison-table {
        direction: rtl;
        border-collapse: collapse;
        width: 100%;
        font-family: -apple-system, "Segoe UI", "Arial Hebrew", Arial, sans-serif;
        font-size: 0.9rem;
        margin: 12px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-radius: 10px;
        overflow: hidden;
    }
    .comparison-table th, .comparison-table td {
        padding: 10px 12px;
        text-align: right;
        vertical-align: top;
        border-bottom: 1px solid #e5e7eb;
        white-space: normal !important;
        word-break: break-word;
        line-height: 1.5;
    }
    .comparison-table th {
        background-color: #1a1f36;
        color: #ffffff;
        font-weight: 700;
        font-size: 0.85rem;
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .comparison-table tbody tr:nth-child(even) {
        background-color: #f9fafb;
    }
    .comparison-table tbody tr:hover {
        background-color: #fef3c7;
    }
    .comparison-table .meta-col {
        background-color: #f3f4f6 !important;
        font-weight: 600;
    }
    .comparison-table .price {
        font-weight: 700;
        font-size: 0.95rem;
        color: #1a1f36;
    }
    .comparison-table .notes {
        font-size: 0.78rem;
        color: #6b7280;
        margin-top: 4px;
    }
    .comparison-table .deviation {
        background: #fef3c7;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        color: #92400e;
        display: inline-block;
        margin-top: 4px;
    }
    .comparison-table .empty {
        color: #d1d5db;
        font-size: 1.2rem;
    }
    </style>
    """

    # --- HTML עם XSS escaping ---
    html_parts = [css, '<table class="comparison-table">']
    # Header
    html_parts.append("<thead><tr>")
    for col in df.columns:
        if col in bank_cols:
            color = bank_color_for_name(col) or "#1a1f36"
            html_parts.append(
                f'<th style="background-color:{esc(color)};color:#fff;'
                f'min-width:140px;">{esc(col)}</th>'
            )
        else:
            html_parts.append(f'<th style="min-width:100px;">{esc(col)}</th>')
    html_parts.append("</tr></thead>")

    # Body
    html_parts.append("<tbody>")
    for _, row in df.iterrows():
        html_parts.append("<tr>")
        for col in df.columns:
            val = str(row[col])
            css_class = "meta-col" if col in meta_cols else ""
            if val == "—":
                html_parts.append(
                    f'<td class="{esc(css_class)}"><span class="empty">—</span></td>')
                continue

            # פיצול לתת-חלקים: מחיר / הערות / חריגה — עם XSS escape
            parts = val.split("\n")
            cell_html = []
            for i, p in enumerate(parts):
                p = p.strip()
                if not p:
                    continue
                if i == 0 and col in bank_cols:
                    cell_html.append(f'<div class="price">{esc(p)}</div>')
                elif "⚠" in p or "שם שונה" in p:
                    cell_html.append(f'<div class="deviation">{esc(p)}</div>')
                else:
                    cell_html.append(f'<div class="notes">{esc(p)}</div>')
            html_parts.append(f'<td class="{esc(css_class)}">{"".join(cell_html)}</td>')
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    return "\n".join(html_parts)


# ========== טאבים ==========
tab_compare, tab_structure, tab_deviation, tab_agent, tab_free, tab_diag = st.tabs([
    "📊 השוואה לפי חלקים",
    "📚 מבנה התעריפון",
    "⚠️ דו\"ח חריגות",
    "🛡️ סוכן תאימות",
    "💬 שיח חופשי",
    "🔍 איבחון",
])

META_COLS_DISPLAY = ["קוד רשמי", "שם העמלה (כללי בנק ישראל)",
                      "בפיקוח", "הערה רגולטורית"]


# ============= TAB 1: השוואה =============
with tab_compare:
    for part in parts_selected:
        st.markdown(f"### {part}")
        st.caption(PARTS_INDEX.get(part, ""))

        df = build_comparison(
            by_bank,
            only_regulated=only_regulated,
            only_with_data=hide_empty,
            parts=[part],
        )
        if df.empty:
            st.info("ℹ️ אין עמלות עם נתונים בחלק הזה.")
            continue

        bank_cols = get_bank_columns(df)
        df = cheapest_per_fee(df, bank_cols)

        ordered = META_COLS_DISPLAY + bank_cols + ["💰 הזול ביותר"]
        df = df[[c for c in ordered if c in df.columns]]

        # רנדור HTML מותאם — טקסט מלא, צבעי בנק
        html = render_html_comparison_table(
            df, bank_cols, META_COLS_DISPLAY + ["💰 הזול ביותר"]
        )
        st.markdown(html, unsafe_allow_html=True)

    # CSV מאוחד
    df_all = build_comparison(by_bank, only_with_data=hide_empty,
                                parts=parts_selected, only_regulated=only_regulated)
    if not df_all.empty:
        st.download_button(
            "⬇️ הורד CSV מלא",
            df_all.to_csv(index=False).encode("utf-8-sig"),
            file_name="comparison_full.csv",
            mime="text/csv",
        )


# ============= TAB 2: מבנה התעריפון =============
with tab_structure:
    st.markdown("### 📚 מבנה התעריפון לפי כללי הבנקאות (נבו)")
    st.caption("עיון בכל 15 החלקים, 5 התוספות ו-5 הנספחים — מספור רשמי + כיסוי פר-בנק.")

    sub1, sub2, sub3 = st.tabs([
        "📖 15 חלקי התוספת הראשונה",
        "📑 5 התוספות",
        "📎 5 הנספחים",
    ])

    with sub1:
        from collections import defaultdict
        coverage = defaultdict(lambda: defaultdict(int))
        total_per_part = defaultdict(int)
        for fee in CANONICAL_FEES:
            total_per_part[fee.part] += 1
            for bank_id, fees in by_bank.items():
                if fee.key in fees:
                    bn = (PROFILES_BY_ID[bank_id].display_name
                          if bank_id in PROFILES_BY_ID else bank_id)
                    coverage[fee.part][bn] += 1

        for part in PARTS_ORDER:
            with st.expander(f"**{part}** ({total_per_part.get(part, 0)} עמלות)"):
                st.caption(PARTS_INDEX.get(part, ""))

                cov = coverage.get(part, {})
                if cov:
                    cov_html = '<div style="display:flex;flex-wrap:wrap;gap:6px;direction:rtl;">'
                    for b, n in sorted(cov.items(), key=lambda x: -x[1]):
                        color = bank_color_for_name(b) or "#888"
                        pct = int(100 * n / total_per_part[part])
                        cov_html += (
                            f'<span style="background:{color};color:#fff;'
                            f'padding:4px 10px;border-radius:14px;'
                            f'font-size:0.82rem;font-weight:600;">'
                            f'{b}: {n} ({pct}%)</span>'
                        )
                    cov_html += "</div>"
                    st.markdown(cov_html, unsafe_allow_html=True)
                    st.markdown("")

                fees_in_part = [f for f in CANONICAL_FEES if f.part == part]
                fee_df = pd.DataFrame([
                    {"קוד": f.code, "שם רשמי": f.he_name,
                     "בפיקוח": "✓" if f.regulated else "",
                     "יחידה": f.unit, "הערה רגולטורית": f.notes}
                    for f in fees_in_part
                ])
                st.dataframe(fee_df, width="stretch", hide_index=True,
                              height=min(500, 60 + 38*len(fee_df)))

    with sub2:
        for name, descr in SUPPLEMENTS.items():
            with st.container(border=True):
                st.markdown(f"### {name}")
                st.markdown(descr)

    with sub3:
        for name, descr in APPENDICES.items():
            with st.container(border=True):
                st.markdown(f"### {name}")
                st.markdown(descr)


# ============= TAB 3: חריגות =============
with tab_deviation:
    st.markdown("### ⚠️ דו\"ח חריגות אוטומטי")
    st.caption(
        "🏷️ שם שונה · ❌ עמלה חסרה · ⚠ עמלה ייחודית · 💸 חריגה בסכום"
    )

    c1, c2 = st.columns([1, 3])
    with c1:
        outlier_factor = st.slider(
            "סף חריגה (×חציון)", 1.5, 5.0, 2.0, 0.25, key="dev_outlier"
        )

    dev_df = build_deviation_report(by_bank, outlier_factor=outlier_factor)
    if dev_df.empty:
        st.success("✓ לא נמצאו חריגות.")
    else:
        with c2:
            counts = dev_df["סוג חריגה"].value_counts()
            cols = st.columns(len(counts))
            for col, (kind, n) in zip(cols, counts.items()):
                col.metric(kind, n)

        st.dataframe(
            dev_df, width="stretch", hide_index=True,
            height=min(700, 50 + len(dev_df) * 38),
            column_config={
                "סוג חריגה": st.column_config.TextColumn(width="small"),
                "קוד רשמי": st.column_config.TextColumn(width="small"),
                "חומרה": st.column_config.TextColumn(width="small"),
                "פרטים": st.column_config.TextColumn(width="large"),
            },
        )
        st.download_button(
            "⬇️ הורד CSV",
            dev_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="deviations.csv", mime="text/csv",
        )


# ============= TAB 4: סוכן תאימות =============
with tab_agent:
    st.markdown("### 🛡️ סוכן ניטור תאימות רגולטורית")

    if "agent_chat" not in st.session_state:
        st.session_state.agent_chat = AgentChat()
    agent = st.session_state.agent_chat

    info_col, scan_col = st.columns([3, 1])
    with info_col:
        st.markdown(
            f"**מבוסס על:** כללי הבנקאות (נבו) + מכתב המפקח 25LM5593 (10.12.2025)<br>"
            f"**מצב הסוכן:** {agent.status()}",
            unsafe_allow_html=True,
        )
    with scan_col:
        if st.button("🔍 הרץ סריקה", type="primary", width="stretch"):
            raw_rows_by_bank = {}
            for f in available:
                d = json.loads(f.read_text(encoding="utf-8"))
                raw_rows_by_bank[d["bank_id"]] = {
                    "unmatched_high_signal": d.get("unmatched_high_signal", [])
                }
            new_findings = scan_compliance(by_bank, raw_rows_by_bank,
                                             price_outlier_factor=3.0)
            merged = merge_with_history(new_findings)
            save_findings(merged)
            st.success(f"✅ זוהו {len(merged)} ממצאים.")

    existing_findings = load_findings()
    if not existing_findings:
        st.warning("טרם בוצעה סריקה. לחץ '🔍 הרץ סריקה'.")
        st.stop()

    # ─── דאשבורד עליון: ציון סיכון פר-בנק ───
    st.divider()
    st.markdown("#### 🏆 ציון סיכון פר-בנק")
    st.caption("גבוה = יותר ממצאים גבוהים. R7 (איכות נתונים) ו-verdict='נדחה' לא משתתפים.")

    risk_scores = bank_risk_scores(existing_findings)
    if risk_scores:
        ranking = sorted(risk_scores.items(), key=lambda x: -x[1]["score"])
        cols = st.columns(min(len(ranking), 5))
        for i, (bank, info) in enumerate(ranking[:5]):
            with cols[i]:
                color = bank_color_for_name(bank) or "#888"
                level = info["level"]
                level_emoji = {"גבוה מאוד": "🔴", "גבוה": "🟠",
                                "בינוני": "🟡", "נמוך": "🟢"}.get(level, "⚪")
                st.markdown(
                    f'<div style="border:2px solid {color};border-radius:10px;'
                    f'padding:12px;text-align:center;background:#fff;">'
                    f'<div style="background:{color};color:#fff;padding:4px 8px;'
                    f'border-radius:6px;font-weight:700;margin-bottom:8px;">{bank}</div>'
                    f'<div style="font-size:1.8rem;font-weight:800;">'
                    f'{info["score"]}</div>'
                    f'<div style="font-size:0.85rem;">'
                    f'{level_emoji} {level} ({info["findings_count"]} ממצאים)</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ─── Top 10 ───
    st.divider()
    st.markdown("#### 🎯 10 הממצאים הקריטיים ביותר")
    top = top_findings(existing_findings, n=10)
    if not top:
        st.success("✓ אין ממצאים קריטיים פתוחים.")
    else:
        for i, f in enumerate(top, start=1):
            color = bank_color_for_name(f.bank) or "#888"
            sev_emoji = {"קריטית": "🔴", "גבוהה": "🟠",
                          "בינונית": "🟡", "נמוכה": "🟢"}.get(f.severity, "⚪")
            rc = RISK_CATEGORIES[f.risk_category]
            # XSS escape — title מגיע מה-PDF
            st.markdown(
                f'<div style="border-right:5px solid {esc(color)};padding:10px 14px;'
                f'margin:6px 0;background:#fff;border-radius:8px;'
                f'box-shadow:0 1px 3px rgba(0,0,0,0.06);">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<strong>#{i} {sev_emoji} {esc(rc["title"])}</strong>'
                f'<span style="background:{esc(color)};color:#fff;padding:3px 10px;'
                f'border-radius:14px;font-size:0.8rem;">{esc(f.bank)}</span></div>'
                f'<div style="color:#374151;margin-top:6px;font-size:0.92rem;">'
                f'{esc(truncate(f.title, 200))}</div></div>',
                unsafe_allow_html=True,
            )

    # ─── מסננים ובחירה ───
    st.divider()
    st.markdown("#### 🗂️ כל הממצאים — ניתוח מפורט")

    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 2, 2])
    with fcol1:
        sev_filter = st.multiselect(
            "חומרה", ["קריטית", "גבוהה", "בינונית", "נמוכה"],
            default=["קריטית", "גבוהה"],
            key="agent_sev",
        )
    with fcol2:
        cat_filter = st.multiselect(
            "קטגוריה",
            options=list(RISK_CATEGORIES.keys()),
            default=[k for k in RISK_CATEGORIES.keys() if k != "R7_DATA_QUALITY"],
            format_func=lambda k: RISK_CATEGORIES[k]["short"],
            key="agent_cat",
        )
    with fcol3:
        bank_filter = st.multiselect(
            "בנק", options=sorted({f.bank for f in existing_findings}),
            default=[], key="agent_bank",
        )
    with fcol4:
        verdict_filter = st.multiselect(
            "סטטוס", ["טרם נבדק", "אושר", "נדחה"],
            default=["טרם נבדק", "אושר"], key="agent_verd",
        )

    def _vl(v): return v if v else "טרם נבדק"
    filtered = [
        f for f in existing_findings
        if f.severity in sev_filter
        and f.risk_category in cat_filter
        and (not bank_filter or f.bank in bank_filter)
        and _vl(f.user_verdict) in verdict_filter
    ]
    st.write(f"📊 **{len(filtered)} ממצאים** עומדים במסננים")

    # ─── פעולות בכמות ───
    with st.expander("⚡ פעולות בכמות", expanded=False):
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            bulk_verdict = st.selectbox(
                "פעולה", ["אישור כממצא אמיתי", "סימון כ-false-positive"],
                key="bulk_v")
        with bcol2:
            scope = st.radio("היקף",
                              ["כל המסונן", "לפי קטגוריה", "לפי בנק"],
                              horizontal=False, key="bulk_s")
        with bcol3:
            st.markdown("&nbsp;")
            if st.button("🔄 הפעל", width="stretch"):
                verdict = "אושר" if bulk_verdict == "אישור כממצא אמיתי" else "נדחה"
                cat = (cat_filter[0] if scope == "לפי קטגוריה"
                       and len(cat_filter) == 1 else None)
                bank = (bank_filter[0] if scope == "לפי בנק"
                        and len(bank_filter) == 1 else None)
                n = bulk_update_verdict(cat, bank, None, verdict)
                st.success(f"עודכנו {n} ממצאים.")
                st.rerun()

    if not filtered:
        st.info("אין ממצאים תואמים למסננים.")
    else:
        find_idx = st.selectbox(
            "בחר ממצא לבחינה מעמיקה",
            options=range(len(filtered)),
            format_func=lambda i: (
                f"[{filtered[i].severity}] "
                f"{RISK_CATEGORIES[filtered[i].risk_category]['short']} | "
                f"{filtered[i].bank} | {filtered[i].title[:70]}"
            ),
            key="agent_finding_idx",
        )
        selected = filtered[find_idx]
        rc = RISK_CATEGORIES[selected.risk_category]
        bank_color = bank_color_for_name(selected.bank) or "#888"
        sev_emoji = {"קריטית": "🔴", "גבוהה": "🟠",
                      "בינונית": "🟡", "נמוכה": "🟢"}.get(selected.severity, "⚪")

        # ─── כרטיס הממצא — XSS escape ───
        st.markdown(
            f'<div style="border:2px solid {esc(bank_color)};border-radius:12px;'
            f'padding:16px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,0.08);">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:10px;">'
            f'<h3 style="margin:0;">{sev_emoji} {esc(rc["title"])}</h3>'
            f'<span style="background:{esc(bank_color)};color:#fff;padding:6px 14px;'
            f'border-radius:18px;font-weight:700;">{esc(selected.bank)}</span></div>'
            f'<div><strong>עמלה:</strong> {esc(selected.fee_name or "-")} '
            f'<code>{esc(selected.fee_code or "—")}</code></div>'
            f'<div><strong>חלק:</strong> {esc(selected.part or "—")}</div>'
            f'<div style="margin:10px 0;color:#374151;">{esc(truncate(selected.description, 1000))}</div>'
            f'<div style="background:#fef3c7;padding:8px 12px;border-radius:6px;'
            f'margin:8px 0;"><strong>⚖️ בסיס משפטי:</strong> {esc(rc["basis"])}</div>'
            f'<div style="background:#fee2e2;padding:8px 12px;border-radius:6px;'
            f'margin:8px 0;"><strong>🚨 חשיפה:</strong> {esc(rc["exposure"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ציטוטים
        if selected.bank_quote:
            st.markdown("**📋 ציטוט מתעריפון הבנק:**")
            st.code(selected.bank_quote, language=None)
        if selected.suggested_action:
            st.markdown("**🎯 פעולה מומלצת:**")
            st.info(selected.suggested_action)

        # ─── השוואה רוחבית של אותה עמלה בכל הבנקים ───
        try:
            comparison = get_comparison_for_finding(selected, by_bank)
        except Exception as e:
            comparison = None
            log_security_event("comparison_failed", str(e), severity="warning")
        if comparison and comparison.get("banks"):
            st.markdown(
                f"### 🌐 השוואה רוחבית — {comparison['fee_name']} "
                f"`{comparison['fee_code']}`"
            )
            stats = comparison.get("stats", {})
            unit = "%" if comparison.get("unit") == "percent" else "₪"

            # שורת סטטיסטיקה
            if "median" in stats:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("חציון השוק", f"{stats['median']:g} {unit}")
                m2.metric(f"זול ביותר", f"{stats['min']:g} {unit}",
                          help=stats.get("cheapest", ""))
                m3.metric(f"יקר ביותר", f"{stats['max']:g} {unit}",
                          help=stats.get("most_expensive", ""))
                m4.metric("בנקים עם נתון", stats["count"])

            # טבלת השוואה ויזואלית עם צבעי בנקים
            comp_rows = []
            max_price = stats.get("max", 1) or 1
            for b in comparison["banks"]:
                if b["price"] is not None:
                    pct_bar = int(100 * b["price"] / max_price) if max_price else 0
                    val_str = f"{b['price']:g} {unit}"
                else:
                    pct_bar = 0
                    # defensive: price_text יכול להיות None
                    pt = b.get("price_text") or "ללא נתון"
                    val_str = pt[:30] if isinstance(pt, str) else "ללא נתון"
                comp_rows.append({
                    "bank": b["bank"], "price": b["price"], "pct": pct_bar,
                    "val_str": val_str,
                    "notes": (b.get("notes") or ""),
                    "highlighted": b["bank"] == selected.bank,
                })

            html = """
            <style>
            .cross-comp { direction: rtl; margin: 12px 0; }
            .cross-comp .row {
                display: grid;
                grid-template-columns: 160px 1fr 100px 100px;
                gap: 12px; align-items: center; padding: 8px 12px;
                border-bottom: 1px solid #eee; font-size: 0.92rem;
            }
            .cross-comp .highlighted {
                background: #fef3c7 !important;
                font-weight: 700;
            }
            .cross-comp .bank-chip {
                padding: 4px 12px; border-radius: 12px;
                color: white; font-weight: 600; font-size: 0.85rem;
                text-align: center;
            }
            .cross-comp .bar {
                height: 22px; border-radius: 4px;
                background: linear-gradient(90deg, var(--c1), var(--c2));
                position: relative;
            }
            .cross-comp .bar-label {
                position: absolute; right: 8px; top: 3px;
                color: white; font-weight: 700; font-size: 0.8rem;
                text-shadow: 0 0 4px rgba(0,0,0,0.5);
            }
            .cross-comp .price-val {
                font-weight: 700; color: #1a1f36; text-align: right;
            }
            .cross-comp .notes { color: #6b7280; font-size: 0.8rem; }
            </style>
            <div class="cross-comp">
            """
            for row in comp_rows:
                color = bank_color_for_name(row["bank"]) or "#888"
                hl = "highlighted" if row["highlighted"] else ""
                # XSS escape כל ערך user-controlled
                html += f"""
                <div class="row {esc(hl)}">
                  <div class="bank-chip" style="background:{esc(color)};">{esc(row['bank'])}</div>
                  <div class="bar" style="--c1:{esc(color)};--c2:{esc(color)}aa;width:{int(row['pct'])}%;">
                    <div class="bar-label">{esc(row['val_str'])}</div>
                  </div>
                  <div class="price-val">{esc(row['val_str'])}</div>
                  <div class="notes">{esc(row['notes'][:30])}</div>
                </div>
                """
            if stats.get("missing"):
                missing_str = ", ".join(esc(m) for m in stats["missing"])
                html += (
                    f'<div style="padding:8px 12px;color:#9ca3af;font-style:italic;">'
                    f'ללא נתון: {missing_str}</div>'
                )
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

            # הצגת תמלילי תווית מקור (לבחינה מעמיקה)
            with st.expander("📄 תוויות מקוריות בכל בנק (איבחון)"):
                for b in comparison["banks"]:
                    src_label = b.get("source_label") or ""
                    if src_label:
                        color = bank_color_for_name(b["bank"]) or "#888"
                        page = b.get("page", "?")
                        price_text = b.get("price_text") or "—"
                        st.markdown(
                            f'<div style="border-right:4px solid {esc(color)};'
                            f'padding:6px 10px;margin:4px 0;background:#fafafa;">'
                            f'<strong>{esc(b["bank"])}</strong> '
                            f'(עמ\' {esc(page)}):<br>'
                            f'<code style="font-size:0.8rem;">'
                            f'{esc(truncate(src_label, 200))}</code><br>'
                            f'<strong>תעריף:</strong> {esc(truncate(price_text, 100))}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        # ─── verdict ───
        vcol1, vcol2, vcol3 = st.columns([1, 1, 2])
        with vcol1:
            if st.button("✅ אשר ליקוי", key=f"approve_{selected.finding_id}",
                          width="stretch"):
                update_verdict(selected.finding_id, "אושר")
                st.rerun()
        with vcol2:
            if st.button("❌ false-positive", key=f"reject_{selected.finding_id}",
                          width="stretch"):
                update_verdict(selected.finding_id, "נדחה")
                st.rerun()
        with vcol3:
            if selected.user_verdict:
                color = "#10b981" if selected.user_verdict == "אושר" else "#ef4444"
                st.markdown(
                    f'<div style="background:{color};color:#fff;padding:8px 16px;'
                    f'border-radius:8px;text-align:center;font-weight:700;">'
                    f'סטטוס: {selected.user_verdict}</div>',
                    unsafe_allow_html=True,
                )

        # ─── שיחה ───
        st.markdown("### 💬 דיון עם הסוכן")

        # שאלות מוצעות - כולל שאלה על השוואה
        followups = agent.suggest_followups(selected)
        if comparison and comparison.get("banks"):
            # החלף את השאלה הראשונה בשאלה על השוואה
            followups = ["הראה השוואה מול בנקים אחרים"] + followups[:2]
        sug_cols = st.columns(len(followups))
        for i, (col, q) in enumerate(zip(sug_cols, followups)):
            with col:
                if st.button(f"💡 {q}", key=f"sug_{selected.finding_id}_{i}",
                              width="stretch"):
                    conv = load_conversation(selected.finding_id)
                    conv.messages.append(ChatMessage(role="user", content=q))
                    reply = agent.respond(selected, conv, q, comparison=comparison)
                    conv.messages.append(ChatMessage(role="assistant", content=reply))
                    save_conversation(conv)
                    st.rerun()

        conv = load_conversation(selected.finding_id)
        for m in conv.messages:
            with st.chat_message("user" if m.role == "user" else "assistant"):
                st.markdown(m.content)

        user_msg = st.chat_input("שאל את הסוכן (כולל 'מה בנקים אחרים גובים?')",
                                   key=f"chat_{selected.finding_id}")
        if user_msg:
            conv.messages.append(ChatMessage(role="user", content=user_msg))
            reply = agent.respond(selected, conv, user_msg, comparison=comparison)
            conv.messages.append(ChatMessage(role="assistant", content=reply))
            save_conversation(conv)
            st.rerun()

        # ─── סיכום וייצוא מייל ───
        # שים לב: מפתחות session_state מתחילים ב-"data_" כדי שלא יתנגשו
        # עם מפתחות הכפתורים (Streamlit שומר את ערך הלחיצה בלולאת המפתח).
        if conv.messages:
            sum_key = f"data_summary_{selected.finding_id}"
            email_key = f"data_email_{selected.finding_id}"
            ecol1, ecol2 = st.columns(2)
            with ecol1:
                if st.button("📝 סכם שיחה", key=f"btn_sum_{selected.finding_id}",
                              width="stretch"):
                    st.session_state[sum_key] = agent.summarize(selected, conv)
            with ecol2:
                if st.button("✉️ הכן מייל למפקח",
                              key=f"btn_email_{selected.finding_id}",
                              width="stretch"):
                    summary = st.session_state.get(sum_key, "")
                    st.session_state[email_key] = \
                        agent.draft_email(selected, conv, summary)

            if sum_key in st.session_state:
                st.markdown("#### 📝 סיכום השיחה")
                st.success(st.session_state[sum_key])

            if email_key in st.session_state:
                st.markdown("#### ✉️ טיוטת מייל")
                email_text = st.session_state[email_key]
                if isinstance(email_text, str):
                    st.text_area("טיוטה (ניתן לערוך):", email_text, height=400,
                                  key=f"ta_email_{selected.finding_id}")
                    st.download_button(
                        "⬇️ הורד טיוטת מייל",
                        email_text.encode("utf-8"),
                        file_name=f"email_{selected.bank}_{selected.finding_id}.txt",
                        mime="text/plain", key=f"dl_email_{selected.finding_id}",
                    )


# ============= TAB 5: שיח חופשי =============
with tab_free:
    st.markdown("### 💬 שיח חופשי עם הסוכן")
    st.caption(
        "שאל את הסוכן כל שאלה על המערכת — הוא ינתח את הנתונים בזמן אמת. "
        "ניתן לשאול: 'מי הכי יקר ב-X?', 'סכם בנק Y', 'הראה 5 ממצאים חמורים'."
    )

    if "agent_chat" not in st.session_state:
        st.session_state.agent_chat = AgentChat()
    if "free_chat_history" not in st.session_state:
        st.session_state.free_chat_history = []
    agent = st.session_state.agent_chat

    # שאלות מהירות
    st.markdown("**שאלות מהירות:**")
    qcols = st.columns(4)
    quick_qs = [
        "אילו בנקים יש במערכת?",
        "הראה 10 ממצאים הכי חריגים",
        "מי הכי זול בעמלות עו\"ש?",
        "אילו עמלות יש בחלק 3?",
    ]
    for col, q in zip(qcols, quick_qs):
        with col:
            if st.button(q, key=f"qq_{q[:15]}", width="stretch"):
                reply = agent.free_chat(q, by_bank,
                                          st.session_state.free_chat_history)
                st.session_state.free_chat_history.append(
                    ChatMessage(role="user", content=q))
                st.session_state.free_chat_history.append(
                    ChatMessage(role="assistant", content=reply))
                st.rerun()

    st.divider()

    # היסטוריית שיחה
    for m in st.session_state.free_chat_history:
        with st.chat_message("user" if m.role == "user" else "assistant"):
            st.markdown(m.content)

    # תיבת שיחה
    user_msg = st.chat_input("שאל את הסוכן כל שאלה על הנתונים…",
                                key="free_chat_input")
    if user_msg:
        st.session_state.free_chat_history.append(
            ChatMessage(role="user", content=user_msg))
        reply = agent.free_chat(user_msg, by_bank,
                                  st.session_state.free_chat_history)
        st.session_state.free_chat_history.append(
            ChatMessage(role="assistant", content=reply))
        st.rerun()

    # ניקוי שיחה
    if st.session_state.free_chat_history:
        if st.button("🗑 נקה שיחה", key="clear_free"):
            st.session_state.free_chat_history = []
            st.rerun()


# ============= TAB 6: איבחון =============
with tab_diag:
    st.markdown("### 🔍 איבחון — מה הופק מכל תעריפון")
    st.caption("מציג מה כל בנק הציע, התווית המקורית, מילת המפתח שזיהתה, וציון ההתאמה.")

    for name in selected_names:
        data = bank_options[name]
        n = len(data["fees"])
        color = bank_color_for_name(name) or "#888"
        with st.expander(
            f"{name} — {n} עמלות מזוהות מתוך {data['raw_row_count']} שורות"
        ):
            if n:
                preview = pd.DataFrame([
                    {
                        "קוד": FEE_BY_KEY[k].code if k in FEE_BY_KEY else "?",
                        "שם רשמי": FEE_BY_KEY[k].he_name if k in FEE_BY_KEY else k,
                        "תווית במקור": v["source_label"],
                        "מילת מפתח": v["matched_keyword"],
                        "ציון": v["match_score"],
                        "מחיר": v["price_text"],
                    }
                    for k, v in data["fees"].items()
                    if k in FEE_BY_KEY
                ])
                st.dataframe(preview, width="stretch", hide_index=True,
                              height=min(500, 60 + 38 * len(preview)))
