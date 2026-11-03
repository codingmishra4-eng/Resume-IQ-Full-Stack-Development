"""
ResumeIQ — Streamlit application entry point.

A polished horizontal top-nav layout (no permanent sidebar) with the pages:
Dashboard · Resume Analyzer · Job Match · AI Improve · Resume Builder ·
Documents · Upgrade.

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


# nav keys are state identifiers; labels/icons are presentation only
NAV = ["Dashboard", "Analyze", "Job Match", "AI Improve", "Resume Builder",
       "History", "Upgrade"]
ICONS = {"Dashboard": "◈", "Analyze": "🧪", "Job Match": "🎯",
         "AI Improve": "✨", "Resume Builder": "🗂", "History": "🕘",
         "Upgrade": "⚡"}
LABELS = {"Dashboard": "Dashboard", "Analyze": "Resume Analyzer",
          "Job Match": "Job Match", "AI Improve": "AI Improve",
          "Resume Builder": "Resume Builder", "History": "Documents",
          "Upgrade": "Upgrade"}


def main() -> None:
    st.set_page_config(page_title=f"{config.APP_NAME} — {config.APP_TAGLINE}",
                       page_icon="◈", layout="wide",
                       initial_sidebar_state="collapsed")
    styles.inject_base_css()
    _init_state()

    _brand_bar()
    _nav_bar()

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
    elif st.session_state.nav == "Upgrade":
        from frontend.pages import pricing
        pricing.render()
    else:
        from frontend.pages import history
        history.render()

    st.markdown(f"<div style='margin-top:34px;'>{components.disclaimer()}</div>",
                unsafe_allow_html=True)


def _brand_bar() -> None:
    st.markdown(
        f"""
<div class="main-enter" style="display:flex;align-items:center;justify-content:space-between;
     padding:16px 4px 8px;flex-wrap:wrap;gap:12px;">
  <div style="display:flex;align-items:center;gap:14px;">
    <div style="width:42px;height:42px;border-radius:13px;flex:none;
         background:linear-gradient(135deg,{styles.C['accent']},{styles.C['accent2']});
         display:flex;align-items:center;justify-content:center;font-size:21px;
         box-shadow:0 6px 18px rgba(16,185,129,.30);">◈</div>
    <div>
      <div style="font-size:21px;font-weight:800;letter-spacing:-0.02em;">{config.APP_NAME}
        <span style="color:{styles.C['muted']};font-weight:500;font-size:12px;
              margin-left:2px;">v{config.APP_VERSION}</span></div>
      <div class="ri-brand-tagline" style="color:{styles.C['muted']};font-size:12px;">{config.APP_TAGLINE}</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:8px;">
    <span class="ri-badge" style="color:{styles.C['green']};background:{styles.C['green']}14;
          border:1px solid {styles.C['green']}44;">
      <span class="ri-dot" style="background:{styles.C['green']};"></span>local-first</span>
    <span class="ri-brand-sub" style="color:{styles.C['muted']};font-size:12px;">your resume stays on your device</span>
  </div>
</div>""",
        unsafe_allow_html=True)


def _nav_bar() -> None:
    """Top navigation pills; the active page gets the green→purple gradient
    (Streamlit `primary` buttons receive the gradient from the design system)."""
    cols = st.columns(len(NAV))
    for col, page in zip(cols, NAV):
        active = st.session_state.nav == page
        with col:
            if st.button(f"{ICONS[page]}  {LABELS[page]}", key=f"nav_{page}",
                         use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.nav = page
                st.rerun()
    st.markdown(
        f"<div class='ri-nav-desc' style='color:{styles.C['muted']};font-size:11.5px;"
        f"margin:2px 0 8px;'>{_desc(st.session_state.nav)}</div>",
        unsafe_allow_html=True)


def _desc(page: str) -> str:
    import html as _html
    DESCRIPTIONS = {
        "Dashboard": "overview, score trend & quick actions",
        "Analyze": "upload a resume & run the full ATS analysis",
        "Job Match": "compare a resume against a job description",
        "AI Improve": "before/after rewrites — accept or reject each one",
        "Resume Builder": "15 templates with live preview & downloads",
        "History": "past analyses, comparisons & saved resumes",
        "Upgrade": "what's free today & what Pro unlocks",
    }
    return _html.escape(DESCRIPTIONS.get(page, ""))


if __name__ == "__main__":
    main()
