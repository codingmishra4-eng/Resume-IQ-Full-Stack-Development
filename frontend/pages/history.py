"""
History page — analysis history, comparisons, saved resumes, trend tracking.

Actions: reopen a full report (from stored JSON), compare any two analyses,
delete records, and re-load saved builder resumes.
"""

from __future__ import annotations

import streamlit as st

from database.database import get_db, record_to_dict
from resume_builder.builder import ResumeBuilder
from resume_builder.resume_data import ResumeData
from frontend import components, styles

_builder = ResumeBuilder()


def render() -> None:
    components.page_title("History", "Past analyses, score comparisons, and saved resumes "
                          "— everything stored locally in SQLite.")
    db = get_db()

    tab_analyses, tab_resumes = st.tabs(["🧪 Analyses", "🗂 Saved resumes"])

    # ------------------------------- analyses -------------------------------
    with tab_analyses:
        records = db.list_analyses()
        if not records:
            st.info("No analyses yet — head to the **Analyze** page to run your first one.")
            return

        table = ""
        for rec in records:
            score = rec.ats_score
            color = (styles.C["green"] if score >= 75 else
                     styles.C["amber"] if score >= 50 else styles.C["red"])
            when = rec.uploaded_at.strftime("%d %b %Y, %H:%M") if rec.uploaded_at else "—"
            match = "—" if rec.job_match_score is None else f"{rec.job_match_score:.0f}%"
            table += f"""
<tr>
  <td style='padding:9px 8px;border-bottom:1px solid {styles.C['border']};font-weight:600;'>
      #{rec.id} · {components.esc(rec.file_name)}</td>
  <td style='padding:9px 8px;border-bottom:1px solid {styles.C['border']};color:{styles.C['muted']};'>{when}</td>
  <td style='padding:9px 8px;border-bottom:1px solid {styles.C['border']};font-weight:800;color:{color};'>{score:.1f}</td>
  <td style='padding:9px 8px;border-bottom:1px solid {styles.C['border']};'>{match}</td>
</tr>"""
        st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:13.5px;margin-bottom:14px;'>
  <tr style='color:{styles.C['muted']};text-transform:uppercase;font-size:11px;
      letter-spacing:.1em;border-bottom:1px solid {styles.C['border']};'>
    <th style='text-align:left;padding:6px 8px;'>File</th>
    <th style='text-align:left;padding:6px 8px;'>When</th>
    <th style='text-align:left;padding:6px 8px;'>ATS score</th>
    <th style='text-align:left;padding:6px 8px;'>Job match</th>
  </tr>{table}</table>""", unsafe_allow_html=True)

        col_load, col_compare, col_delete = st.columns(3, gap="medium")
        with col_load:
            st.markdown("#### 📄 Reopen a report")
            rec_id = st.selectbox("Pick analysis",
                                  [r.id for r in records],
                                  format_func=lambda rid: f"#{rid} · {next(r.file_name for r in records if r.id == rid)}")
            if st.button("Open full report", use_container_width=True):
                st.session_state["history_view"] = int(rec_id)
        with col_compare:
            st.markdown("#### 📊 Compare two analyses")
            pair = st.multiselect("Pick two", [r.id for r in records],
                                  format_func=lambda rid: f"#{rid}", max_selections=2)
            if len(pair) == 2:
                a, b = get_analysis(record_to_dict, pair[0]), get_analysis(record_to_dict, pair[1])
                if a and b:
                    _compare(a, b)
        with col_delete:
            st.markdown("#### 🗑 Delete a record")
            del_id = st.selectbox("Pick analysis", [r.id for r in records],
                                  key="del_rec",
                                  format_func=lambda rid: f"#{rid} · {next(r.file_name for r in records if r.id == rid)}")
            if st.button("Delete permanently", use_container_width=True):
                db.delete_analysis(int(del_id))
                st.success(f"Deleted #{del_id}.")
                st.rerun()

        if st.session_state.get("history_view"):
            _full_report(st.session_state["history_view"], db)

    # ------------------------------- resumes ---------------------------------
    with tab_resumes:
        saved = db.list_resumes()
        if not saved:
            st.info("No saved builder resumes yet — create one in the **Resume Builder**.")
        else:
            grid = st.columns(3, gap="medium")
            for i, rec in enumerate(saved):
                with grid[i % 3]:
                    tpl = _builder.templates.get(rec.template_id)
                    st.markdown(f"""
<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
     border-radius:16px;padding:16px;'>
  <div style='font-weight:700;'>{components.esc(rec.name)}</div>
  <div style='color:{styles.C['muted']};font-size:12.5px;margin-top:3px;'>
    {components.esc(tpl.name if tpl else rec.template_id)} · updated
    {(rec.updated_at.strftime('%d %b %Y') if rec.updated_at else '—')}</div>
</div>""", unsafe_allow_html=True)
                    cc1, cc2 = st.columns(2)
                    if cc1.button("Open in builder", key=f"hr_open_{rec.id}"):
                        st.session_state["resume_data"] = rec.data_json
                        st.session_state["template_id"] = rec.template_id
                        st.session_state["nav"] = "Resume Builder"
                        st.rerun()
                    if cc2.button("Delete", key=f"hr_del_{rec.id}"):
                        db.delete_resume(rec.id)
                        st.rerun()


def get_analysis(sub, rid: int):
    rec = get_db().get_analysis(rid)
    return record_to_dict(rec) if rec else None


def _compare(a: dict, b: dict) -> None:
    cats = a.get("scores", {})
    cats_b = b.get("scores", {})
    rows = ""
    for k in cats:
        va, vb = cats[k], cats_b.get(k, 0)
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
<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};border-radius:14px;padding:14px 18px;'>
<div style='font-weight:700;margin-bottom:6px;'>#{a['id']} → #{b['id']} · overall
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
        ats = report.get("ats", {})
        st.markdown(components.category_bars({
            k: cat.get("score", 0) for k, cat in (ats.get("categories") or {}).items()
        }), unsafe_allow_html=True)
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
