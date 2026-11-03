"""
Job Match page — dedicated side-by-side JD ↔ resume comparison.

Accepts the last analyzed resume, a fresh upload, or pasted text, then runs
the matcher entirely on-device. Results: match %, matching / partial /
missing skills, JD vocabulary and honest guidance notes.
"""

from __future__ import annotations

import streamlit as st

from backend.job_matcher import JobMatcher
from backend.keyword_analyzer import KeywordAnalyzer
from backend.resume_parser import ParsedResume, ParseError, ResumeParser
from frontend import components, styles

_parser = ResumeParser()
_matcher = JobMatcher(KeywordAnalyzer())


def render() -> None:
    components.page_title("Job Match", "See exactly which job requirements your resume "
                          "covers, partially covers, or misses — computed from your real text.",
                          eyebrow="matcher")

    # ---------------- inputs -------------------------------------------------
    src_col, jd_col = st.columns([1, 2.2], gap="medium")

    resume_text: str | None = None
    resume_name = ""

    with src_col:
        st.markdown("**1 · Resume**")
        last = st.session_state.get("analysis")
        if last is not None:
            if st.button(f"♻  Use last analyzed ({last.parsed.file_name})",
                         key="jm_use_last", use_container_width=True):
                st.session_state["jm_source_mode"] = "last"
        mode_file = st.file_uploader("…or upload a PDF / DOCX", type=["pdf", "docx"], key="jm_file")
        mode_paste = st.text_area("…or paste resume text", height=110, key="jm_paste")

        if mode_file is not None:
            try:
                parsed = _parser.parse(mode_file.getvalue(), mode_file.name)
                resume_text, resume_name = parsed.text, parsed.file_name
            except ParseError as exc:
                st.error(f"❌ {exc}")
        elif mode_paste and mode_paste.strip():
            resume_text, resume_name = mode_paste, "pasted text"
        elif st.session_state.get("jm_source_mode") == "last" and last is not None:
            resume_text, resume_name = last.parsed.text, last.parsed.file_name

    with jd_col:
        st.markdown("**2 · Job description**")
        jd_text = st.text_area("Paste the full job description", height=280, key="jm_jd",
                               placeholder="Paste the job description you're targeting…")
        jd_file = st.file_uploader("…or upload a .txt / .pdf job description",
                                   type=["txt", "pdf"], key="jm_jdf")
        if jd_file and not jd_text:
            jd_text = _extract_jd_file(jd_file)

    agree = st.button("🎯 Match resume ↔ job", type="primary")

    if not agree:
        _render_info_card()
        return

    if not resume_text:
        st.error("Provide a resume — upload a file, paste text, or click “Use last analyzed”.")
        return
    if not jd_text or len(jd_text.split()) < 10:
        st.error("Paste a job description first (a few sentences at minimum).")
        return

    with st.spinner("Comparing resume with the job description…"):
        # Parse (or reuse) a rich ParsedResume; fall back to plain text parsing.
        parsed = None
        if st.session_state.get("jm_source_mode") == "last" and last is not None \
                and last.parsed.text == resume_text:
            parsed = last.parsed
        try:
            if parsed is None and mode_file is not None:
                parsed = _parser.parse(mode_file.getvalue(), mode_file.name)
        except ParseError:
            parsed = None
        if parsed is None:
            parsed = ParsedResume(file_name=resume_name or "pasted", file_type="txt",
                                  text=resume_text, pages=0)
            _parser._enrich(parsed)

        result = _matcher.match(parsed, jd_text)
        st.session_state["jm_result"] = result
        st.session_state["jm_resume"] = parsed

    st.divider()
    _render_match()


# --------------------------------------------------------------------------- #
def _render_match() -> None:
    match = st.session_state.get("jm_result")
    if match is None:
        st.info("Run a match first.")
        return

    score_color = (styles.C["green"] if match.match_score >= 75 else
                   styles.C["amber"] if match.match_score >= 50 else styles.C["red"])

    # ---- score header ------------------------------------------------------
    c1 = st.columns([1, 3])[0]
    with c1:
        st.markdown(f"""<div class="ri-card" style="padding:22px;text-align:center;">
            <div style="width:118px;height:118px;margin:0 auto;border-radius:50%;
                 background:conic-gradient({score_color} {match.match_score * 3.6:.1f}deg,
                 rgba(148,163,184,.14) 0deg);display:flex;align-items:center;justify-content:center;">
              <div style="width:92px;height:92px;border-radius:50%;background:{styles.C['card']};
                   display:flex;align-items:center;justify-content:center;">
                <span style="font-size:26px;font-weight:800;color:{score_color};
                      font-family:'JetBrains Mono',monospace;">{match.match_score:.0f}%</span>
              </div>
            </div>
            <div class="ri-eyebrow" style="margin-top:10px;">heuristic match estimate</div>
            <div style="margin-top:6px;font-size:14px;font-weight:600;">
            {components.esc(match.job_title or 'Unnamed role')}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("### Side-by-side comparison")
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown("#### 💼 Your resume shows")
        if match.resume_categories:
            cards = "".join(
                f"<div class='ri-card' style='padding:12px 16px;flex:1;min-width:200px;'>"
                f"<div class='ri-eyebrow'>{components.esc(category)}</div>"
                f"<div style='margin-top:6px;'>"
                f"{components.skill_chips(skills, styles.C['green'])}</div></div>"
                for category, skills in sorted(match.resume_categories.items()) if skills)
            st.markdown(f"<div class='ri-flexwrap'>{cards}</div>", unsafe_allow_html=True)
        else:
            st.caption("No taxonomy skills detected in this resume. Use precise names like "
                       "“Python”, “SQL”, “Figma”.")
    with right:
        st.markdown(f"#### 🧾 The job asks for ({match.job_title or 'role'})")
        if match.jd_categories:
            cards = "".join(
                f"<div class='ri-card' style='padding:12px 16px;flex:1;min-width:200px;'>"
                f"<div class='ri-eyebrow'>{components.esc(category)}</div>"
                f"<div style='margin-top:6px;'>"
                f"{components.skill_chips(skills, styles.C['highlight'])}</div></div>"
                for category, skills in sorted(match.jd_categories.items()) if skills)
            st.markdown(f"<div class='ri-flexwrap'>{cards}</div>", unsafe_allow_html=True)
        else:
            st.caption("No taxonomy skills detected in this JD.")

    st.markdown("### Skill match detail")
    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        _skill_panel("✅ Matching", match.matching, styles.C["green"],
                     f"{len(match.matching)} requirement(s) hit exactly")
    with col2:
        _skill_panel("🟡 Partial", match.partial, styles.C["amber"],
                     "Related same-domain skills exist in your resume but the JD's exact term "
                     "doesn't — consider using the JD wording when truthful.")
    with col3:
        _skill_panel("❌ Missing", match.missing, styles.C["red"],
                     "Absent from your resume — listed as gaps, never as your skills.")

    if match.jd_extra_keywords:
        st.markdown("#### 🔑 JD vocabulary not in your resume")
        st.markdown(components.skill_chips(match.jd_extra_keywords, styles.C["accent2"]),
                    unsafe_allow_html=True)
        st.caption("Weave these in naturally across your summary and bullets — ONLY where you "
                   "genuinely have the experience. Do not stuff keywords.")

    if match.min_years:
        st.warning(f"🧮 The JD mentions roughly {match.min_years[0]}+ years of experience — "
                   f"only claim what you actually have.", icon="ℹ️")
    if match.degree_requirements:
        st.markdown("🎓 **Education terms found in the JD:** " +
                    components.skill_chips(match.degree_requirements, styles.C["muted"], "14"),
                    unsafe_allow_html=True)

    st.markdown("#### 🧭 Notes & guidance")
    for note in match.notes:
        st.markdown(f"<div style='font-size:13px;margin:4px 0;'>ℹ️ {components.esc(note)}</div>",
                    unsafe_allow_html=True)

    st.info("✍️ Open the **AI Improve** page to rewrite specific bullets around these gaps — "
            "every suggestion stays grounded in skills you already listed.",
            icon="🧠")


def _skill_panel(title: str, skills: list[str], color: str, note: str) -> None:
    st.markdown(
        f"<div class='ri-card' style='padding:14px 16px;height:100%;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-weight:700;font-size:14px;'>{components.esc(title)}</span>"
        f"<span class='ri-mono' style='font-size:14px;font-weight:800;color:{color};'>"
        f"{len(skills)}</span></div>"
        f"<div style='margin-top:8px;'>{components.skill_chips(skills, color)}</div>"
        f"<div style='color:{styles.C['muted']};font-size:11.5px;margin-top:8px;line-height:1.5;'>"
        f"{components.esc(note)}</div></div>", unsafe_allow_html=True)


def _render_info_card() -> None:
    c = styles.C
    st.markdown(f"""<div class='ri-card' style='padding:20px 24px;line-height:1.8;color:{c['muted']};'>
      <div style='font-weight:700;color:{c['text']};margin-bottom:6px;'>How matching works</div>
      <div>1 · Every taxonomy skill the job description asks for is detected from its text.</div>
      <div>2 · Your resume is scanned for the same skills.</div>
      <div>3 · Skills absent from your resume are listed as <b style="color:{c['text']};">missing</b>,
      never as your skills.</div>
      <div>4 · The match % weighs skill coverage (70%) and general JD keyword coverage (30%).
      It is a <b style="color:{c['text']};">heuristic estimate</b>, not a guarantee.</div>
    </div>""", unsafe_allow_html=True)


def _extract_jd_file(file) -> str:
    """Extract JD text from a .txt or .pdf upload (defensive)."""
    data = file.getvalue()
    if file.name.lower().endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    try:
        import pymupdf
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(page.get_text() or "" for page in doc)
        doc.close()
        return text
    except Exception:                                       # noqa: BLE001
        st.error("Could not read that job-description file — paste the text instead.")
        return ""
