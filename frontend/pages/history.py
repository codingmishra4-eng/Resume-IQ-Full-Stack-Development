"""
Documents page — analysis history ("Documents"), comparisons, saved resumes.

Actions: reopen a full report (from stored JSON), compare any two analyses,
delete records, and re-load / delete saved builder resumes. A search box
filters both tables against real SQLite data.
"""

from __future__ import annotations

import streamlit as st

from database.database import get_db, record_to_dict
from resume_builder.builder import ResumeBuilder
from resume_builder.resume_data import ResumeData
from frontend import components, styles
from frontend.pages.builder import clear_builder_widget_cache

_builder = ResumeBuilder()


def _matches(haystack: str, query: str) -> bool:
    return (not query) or (query.lower() in (haystack or "").lower())


def render() -> None:
    components.page_title("Documents", "Analyses, score comparisons and saved resumes "
                          "— every record live from your local SQLite database.",
                          eyebrow="documents")
    db = get_db()

    tab_all, tab_analyses, tab_resumes = st.tabs(
        ["🗂 All documents", "🧪 Analyses", "📄 Saved resumes"])

    with tab_all:
        _all_documents(db)
    with tab_analyses:
        _analyses_tab(db)
    with tab_resumes:
        _resumes_tab(db)


# --------------------------------------------------------------------------- #
def _all_documents(db) -> None:
    """Merged view: every analysis + saved resume in one searchable table."""
    query = st.text_input("Search by document name",
                          placeholder="Type to filter — e.g. “kavya” or “report”",
                          key="doc_search")

    records = [r for r in db.list_analyses()
               if _matches(r.file_name, query)]
    saved = [r for r in db.list_resumes()
             if _matches(r.name, query)]

    counts = st.columns(2, gap="medium")
    with counts[0]:
        st.markdown(components.badge(f"{len(records)} analyses", styles.C["highlight"]),
                    unsafe_allow_html=True)
    with counts[1]:
        st.markdown(components.badge(f"{len(saved)} saved resumes", styles.C["accent"]),
                    unsafe_allow_html=True)

    if not records and not saved:
        components.empty_state("🗂", "No documents match",
                               "Adjust the search above, or create your first document "
                               "from the Resume Analyzer / Resume Builder pages.")
        return

    rows = []
    for rec in records:
        when = rec.uploaded_at.strftime("%d %b %Y, %H:%M") if rec.uploaded_at else "—"
        color = (styles.C["green"] if rec.ats_score >= 75 else
                 styles.C["amber"] if rec.ats_score >= 50 else styles.C["red"])
        rows.append([
            components.esc(rec.file_name),
            f"<span class='ri-badge' style='color:{styles.C['highlight']};"
            f"background:{styles.C['highlight']}14;border:1px solid "
            f"{styles.C['highlight']}44;'>analysis</span>",
            f"<span style='color:{styles.C['muted']}'>{when}</span>",
            f"<span class='ri-mono' style='font-weight:800;color:{color};'>"
            f"{rec.ats_score:.1f}</span>",
            f"<span style='color:{styles.C['muted']};'>view / compare / delete → Analyses tab</span>",
        ])
    for rec in saved:
        when = rec.updated_at.strftime("%d %b %Y, %H:%M") if rec.updated_at else "—"
        tpl = _builder.templates.get(rec.template_id)
        rows.append([
            components.esc(rec.name),
            f"<span class='ri-badge' style='color:{styles.C['accent']};"
            f"background:{styles.C['accent']}14;border:1px solid "
            f"{styles.C['accent']}44;'>resume</span>",
            f"<span style='color:{styles.C['muted']}'>{when}</span>",
            f"<span style='color:{styles.C['muted']}'>—</span>",
            f"<span style='color:{styles.C['muted']};'>open / delete → Saved resumes tab</span>",
        ])

    st.markdown(components.data_table(
        ["Name", "Type", "Last modified", "Score", "Actions"], rows),
        unsafe_allow_html=True)


def _analyses_tab(db) -> None:
    records = db.list_analyses()
    if not records:
        components.empty_state("🧪", "No analyses yet",
                               "Head to the Resume Analyzer to run your first analysis — "
                               "results are stored here permanently.")
        return

    rows = []
    for rec in records:
        score = rec.ats_score
        color = (styles.C["green"] if score >= 75 else
                 styles.C["amber"] if score >= 50 else styles.C["red"])
        when = rec.uploaded_at.strftime("%d %b %Y, %H:%M") if rec.uploaded_at else "—"
        match = "—" if rec.job_match_score is None else f"{rec.job_match_score:.0f}%"
        rows.append(f"""
<tr>
  <td style='padding:10px 12px;font-weight:600;'>#{rec.id} · {components.esc(rec.file_name)}</td>
  <td style='padding:10px 12px;color:{styles.C['muted']};'>{when}</td>
  <td style='padding:10px 12px;font-weight:800;color:{color};'>{score:.1f}</td>
  <td style='padding:10px 12px;'>{match}</td>
</tr>""")
    st.markdown(components.data_table(
        ["File", "When", "ATS score", "Job match"], rows),
        unsafe_allow_html=True)

    col_load, col_compare, col_delete = st.columns(3, gap="medium")
    with col_load:
        st.markdown("**📄 Reopen a report**")
        rec_id = st.selectbox("Pick analysis",
                              [r.id for r in records],
                              format_func=lambda rid: f"#{rid} · {next(r.file_name for r in records if r.id == rid)}",
                              key="view_rec")
        if st.button("Open full report", use_container_width=True):
            st.session_state["history_view"] = int(rec_id)
    with col_compare:
        st.markdown("**📊 Compare two analyses**")
        pair = st.multiselect("Pick two", [r.id for r in records],
                              format_func=lambda rid: f"#{rid}", max_selections=2)
        if len(pair) == 2:
            a, b = get_analysis(record_to_dict, pair[0]), get_analysis(record_to_dict, pair[1])
            if a and b:
                _compare(a, b)
    with col_delete:
        st.markdown("**🗑 Delete a record**")
        del_id = st.selectbox("Pick analysis", [r.id for r in records],
                              key="del_rec",
                              format_func=lambda rid: f"#{rid} · {next(r.file_name for r in records if r.id == rid)}")
        if st.button("Delete permanently", use_container_width=True):
            db.delete_analysis(int(del_id))
            st.success(f"Deleted #{del_id}.")
            st.rerun()

    if st.session_state.get("history_view"):
        _full_report(st.session_state["history_view"], db)


def get_analysis(sub, rid: int):
    rec = get_db().get_analysis(rid)
    return record_to_dict(rec) if rec else None


def _resumes_tab(db) -> None:
    saved = db.list_resumes()
    if not saved:
        components.empty_state("🗂", "No saved builder resumes yet",
                               "Create one in the Resume Builder and save it — "
                               "it will appear here and in “All documents”.")
        return
    grid = st.columns(3, gap="medium")
    for i, rec in enumerate(saved):
        with grid[i % 3]:
            tpl = _builder.templates.get(rec.template_id)
            st.markdown(f"""
<div class="ri-card ri-lift" style="padding:16px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
    <div style="font-weight:700;">{components.esc(rec.name)}</div>
    {components.badge("resume", styles.C['accent'])}
  </div>
  <div style="color:{styles.C['muted']};font-size:12.5px;margin-top:4px;">
    {components.esc(tpl.name if tpl else rec.template_id)} · updated
    {(rec.updated_at.strftime('%d %b %Y') if rec.updated_at else '—')}</div>
</div>""", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            if cc1.button("Open in builder", key=f"hr_open_{rec.id}"):
                clear_builder_widget_cache()
                st.session_state["resume_data"] = rec.data_json
                st.session_state["template_id"] = rec.template_id
                st.session_state["nav"] = "Resume Builder"
                st.rerun()
            if cc2.button("Delete", key=f"hr_del_{rec.id}"):
                db.delete_resume(rec.id)
                st.rerun()


def _compare(a: dict, b: dict) -> None:
    rows = ""
    for k in a.get("scores", {}):
        va, vb = a["scores"][k], b.get("scores", {}).get(k, 0)
        delta = vb - va
        arrow = ("▲" if delta > 0 else "▼" if delta < 0 else "=")
        color = styles.C["green"] if delta > 0 else styles.C["red"] if delta < 0 else styles.C["muted"]
        rows += (f"<tr><td style='padding:6px 4px;border-bottom:1px solid {styles.C['border']}'>"
                 f"{k.title()}</td>"
                 f"<td style='padding:6px 4px;border-bottom:1px solid {styles.C['border']}'>{va:.0f}</td>"
                 f"<td style='padding:6px 4px;border-bottom:1px solid {styles.C['border']}'>{vb:.0f}</td>"
                 f"<td style='padding:6px 4px;border-bottom:1px solid {styles.C['border']};color:{color};'>"
                 f"{arrow} {abs(delta):.0f}</td></tr>")
    st.markdown(f"""
<div class="ri-card" style="padding:14px 18px;">
<div style="font-weight:700;margin-bottom:6px;">#{a['id']} → #{b['id']} · overall
{a['ats_score']:.0f} → <b>{b['ats_score']:.0f}</b></div>
<table style='width:100%;border-collapse:collapse;font-size:12.5px;'>
{rows}</table></div>""", unsafe_allow_html=True)


def _full_report(rid: int, db) -> None:
    rec = db.get_analysis(rid)
    if not rec:
        st.warning("That record no longer exists.")
        del st.session_state["history_view"]
        return
    report = rec.report_json or {}
    with st.expander(f"📌 Full report — #{rec.id} {rec.file_name}", expanded=True):
        st.markdown(f"**Estimated ATS score: {rec.ats_score:.1f}** · "
                    f"{rec.word_count} words · {rec.file_type.upper()} · "
                    f"analyzed {(rec.uploaded_at.strftime('%d %b %Y') if rec.uploaded_at else '')}")
        st.markdown(components.category_bars({
            k: cat.get("score", 0) for k, cat in (report.get("ats", {}).get("categories") or {}).items()
        }), unsafe_allow_html=True)
        ats = report.get("ats", {})
        lc, wc = st.columns(2, gap="medium")
        with lc:
            st.markdown("**Strengths**")
            st.write(ats.get("strengths") or ["—"])
        with wc:
            st.markdown("**Weaknesses**")
            st.write(ats.get("weaknesses") or ["—"])
        st.markdown("**Recommendations**")
        for i, tip in enumerate(ats.get("recommendations") or [], 1):
            st.markdown(f"{i}. {tip}")
        st.caption(report.get("disclaimer", ""))
        if st.button("Load text into AI Improve", key=f"hv_{rid}"):
            st.session_state["analysis_used_default"] = True
            st.session_state["nav"] = "AI Improve"
            st.rerun()
