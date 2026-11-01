"""
ResumeIQ — Streamlit application entry point.

A fast, horizontal top-nav layout (no permanent sidebar) with the six pages:
Dashboard · Analyze · Job Match · AI Improve · Resume Builder · History.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import config
from frontend import components, styles


# Session-state bootstrap (shared across pages)
def _init_state() -> None:
    for key, default in {
        "nav": "Dashboard",
        "analysis": None,          # FullAnalysis object from scoring engine
        "ai_status_shown": False,
        "resume_data": None,       # builder form data (dict)
        "last_report_pdf": None,   # path to the generated report
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default


NAV = ["Dashboard", "Analyze", "Job Match", "AI Improve", "Resume Builder", "History"]
ICONS = {"Dashboard": "◈", "Analyze": "🧪", "Job Match": "🎯",
         "AI Improve": "✨", "Resume Builder": "🗂", "History": "🕘"}
DESCRIPTIONS = {
    "Dashboard": "overview, score trend & quick actions",
    "Analyze": "upload a resume & run the full ATS analysis",
    "Job Match": "compare a resume against a job description",
    "AI Improve": "before/after rewrites — accept or reject each one",
    "Resume Builder": "15 templates with live preview & downloads",
    "History": "past analyses, comparisons & saved resumes",
}


def main() -> None:
    st.set_page_config(page_title=f"{config.APP_NAME} — {config.APP_TAGLINE}",
                       page_icon="◈", layout="wide",
                       initial_sidebar_state="collapsed")
    styles.inject_base_css()
    _init_state()

    # ---- hero / brand bar ----
    st.markdown(
        f"""
<div class="main-enter" style="display:flex;align-items:center;justify-content:space-between;
     padding:14px 4px 6px;flex-wrap:wrap;gap:12px;">
  <div style="display:flex;align-items:center;gap:14px;">
    <div style="width:44px;height:44px;border-radius:14px;flex:none;
         background:linear-gradient(135deg,{styles.C['accent']},#22d3ee);
         display:flex;align-items:center;justify-content:center;font-size:22px;">◈</div>
    <div>
      <div style="font-size:21px;font-weight:800;letter-spacing:-0.02em;">{config.APP_NAME}
        <span style="color:{styles.C['muted']};font-weight:500;font-size:13px;">v{config.APP_VERSION}</span></div>
      <div style="color:{styles.C['muted']};font-size:12.5px;">{config.APP_TAGLINE}</div>
    </div>
  </div>
  <div style="color:{styles.C['muted']};font-size:12px;">Local-first · your resume stays on your device</div>
</div>""",
        unsafe_allow_html=True)

    # ---- top navigation (buttons in one row) ----
    cols = st.columns(len(NAV))
    for col, page in zip(cols, NAV):
        active = st.session_state.nav == page
        with col:
            label = f"{ICONS[page]} **{page}**" if active else f"{ICONS[page]} {page}"
            if st.button(label, key=f"nav_{page}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.nav = page
                st.rerun()
    st.markdown(
        f"<div style='color:{styles.C['muted']};font-size:12px;margin:0 0 10px;'>"
        f"{esc_min(DESCRIPTIONS[st.session_state.nav])}</div>",
        unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 18px;'>", unsafe_allow_html=True)

    # ---- routers (imported lazily so pages stay lightweight) ----
    if st.session_state.nav == "Dashboard":
        from frontend.pages import dashboard
        dashboard.render()
    elif st.session_state.nav == "Analyze":
        from frontend.pages import analyze
        analyze.render()
    elif st.session_state.nav == "Job Match":
        from frontend.pages import job_match
        job_match.render()
    elif st.session_state.nav == "AI Improve":
        from frontend.pages import improve
        improve.render()
    elif st.session_state.nav == "Resume Builder":
        from frontend.pages import builder
        builder.render()
    else:
        from frontend.pages import history
        history.render()

    st.divider()
    st.caption(f"{config.APP_NAME} · scores are estimated ATS-compatibility heuristics, "
               f"not official ATS vendor results.")


def esc_min(text: str) -> str:
    import html as _html
    return _html.escape(text or "")


if __name__ == "__main__":
    main()
