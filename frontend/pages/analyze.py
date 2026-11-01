"""
Analyze page — upload a resume (PDF/DOCX), optional job description,
run the six-category ATS analysis and explore/discover the full report.
"""

from __future__ import annotations

import streamlit as st

import config
from backend.scoring_engine import ScoringEngine
from frontend import components, styles


def render() -> None:
    components.page_title("Analyze Resume", "Upload a PDF or DOCX to score its estimated "
                          "ATS compatibility — everything runs on your machine.")

    engine = ScoringEngine()
    if not engine.ai.ai_available:
        _ai_notice()

    # ---- upload form ----
    with st.container():
        up_col, jd_col = st.columns([1.25, 1], gap="medium")
        with up_col:
            file = st.file_uploader("Resume file (PDF or DOCX, max 10 MB)",
                                    type=["pdf", "docx"], accept_multiple_files=False)
        with jd_col:
            jd_text = st.text_area(
                "Job description (optional — enables keyword scoring)",
                height=130,
                placeholder="Paste the job description here for relevance scoring...")

        run = st.button("🧪 Run full analysis", type="primary", use_container_width=False)

        if run:
            if file is None:
                st.error("Please upload a PDF or DOCX resume first.")
            else:
                _run_analysis(engine, file, jd_text)

    # ---- results ----
    if st.session_state.get("analysis"):
        _render_results()


def _ai_notice() -> None:
    st.info("🤖 OpenAI key not configured — running in **rule-based mode**. "
            "Every score and finding is still computed from your actual document; "
            "AI-narrated suggestions are simply replaced by rule-generated ones. "
            "See `.env.example` to enable AI features.", icon="ℹ️")


def _run_analysis(engine, file, jd_text: str) -> None:
    st.session_state.analysis = None
    st.session_state.last_report_pdf = None

    progress = st.progress(0.0, text="Reading document…")
    try:
        data = file.getvalue()
        name = file.name

        progress.progress(0.35, text="Extracting text & structure…")
        from backend.resume_parser import ResumeParser
        parser = ResumeParser()
        parsed = parser.parse(data, name)

        progress.progress(0.65, text="Scoring six ATS categories…")
        ats = engine.analyzer.analyze(parsed, job_description=(jd_text or None))
        job_match = engine.matcher.match(parsed, jd_text) if jd_text else None
        from backend.scoring_engine import FullAnalysis
        analysis = FullAnalysis(parsed=parsed, ats=ats, job_match=job_match)

        progress.progress(0.9, text="Saving to history & building the report…")
        categories = analysis.category_scores
        record = engine.db.save_analysis({        # persist for history
            "file_name": parsed.file_name, "file_type": parsed.file_type,
            "ats_score": ats.overall,
            "readability_score": categories.get("readability", 0.0),
            "structure_score": categories.get("structure", 0.0),
            "completeness_score": categories.get("completeness", 0.0),
            "keywords_score": categories.get("keywords", 0.0),
            "formatting_score": categories.get("formatting", 0.0),
            "contact_score": categories.get("contact", 0.0),
            "word_count": parsed.word_count,
            "job_match_score": job_match.match_score if job_match else None,
            "report_json": analysis.report_dict(), "resume_text": parsed.text[:150_000],
        })
        analysis.record_id = record.id

        from resume_builder.report_pdf import ReportPDFBuilder
        path = ReportPDFBuilder().build(
            analysis.report_dict(), config.GENERATED_DIR / f"analysis_report_{record.id}.pdf")
        st.session_state.last_report_pdf = str(path)
        st.session_state.analysis = analysis
        st.session_state.nav = "Analyze"

        progress.progress(1.0, text="Done ✓")
        st.success(f"Analysis complete — estimated ATS score **{ats.overall:.1f}** "
                   f"saved to history (record #{record.id}).")
        st.rerun()
    except Exception as exc:                    # noqa: BLE001 — surface a clean UI error
        progress.empty()
        if type(exc).__name__ == "ParseError":
            st.error(f"❌ {exc}")
        else:
            import logging
            logging.getLogger("analyze_page").exception("Analysis failed")
            st.error(f"❌ Analysis failed unexpectedly: `{type(exc).__name__}` — "
                     "check `logs/resumeiq.log` for details.")
    return


def _render_results() -> None:
    analysis = st.session_state.analysis
    parsed, ats, match = analysis.parsed, analysis.ats, analysis.job_match

    st.divider()
    st.markdown("### 📊 Results")

    # score ring + category bars
    components.score_ring(ats.overall)
    st.markdown(components.category_bars(analysis.category_scores), unsafe_allow_html=True)

    # download report
    if st.session_state.get("last_report_pdf"):
        with open(st.session_state.last_report_pdf, "rb") as fh:
            st.download_button("⬇  Download full PDF report", fh,
                               file_name="resumeiq_report.pdf", mime="application/pdf")

    # ---- strengths / weaknesses / recommendations ----
    s1, s2, s3 = st.columns(3, gap="medium")
    with s1:
        st.markdown("##### 💪 Strengths")
        _bulleted(ats.strengths, "✔")
    with s2:
        st.markdown("##### 🧭 Weaknesses")
        _bulleted(ats.weaknesses, "▲")
    with s3:
        st.markdown("##### ✅ Top recommendations")
        _bulleted(ats.recommendations[:6], "→", numbered=True)

    # ---- category detail (expandable, verified notation) ----
    st.markdown("#### Category breakdown")
    nice = {"readability": "📖 Readability & parseability",
            "structure": "🧱 Structure & sections",
            "completeness": "📋 Content completeness",
            "keywords": "🔑 Keywords & vocabulary",
            "formatting": "🎯 Formatting compatibility",
            "contact": "📞 Contact information"}
    limiters = {"keywords": ("Heuristic keywords from ResumeIQ's skill taxonomy — "
                             "verify relevance yourself."),
                "structure": ("Section names are pattern-matched; custom/unusual headings may "
                              "not be recognised (heuristic).")}
    for key, cat in ats.categories.items():
        label = (f"{nice.get(key, key)} — {cat.score:.0f}/100 "
                 f"({100 * cat.weight:.0f}% weight)")
        with st.expander(label, expanded=cat.score < 60):
            st.markdown(components.checks_table(cat.checks), unsafe_allow_html=True)
            if key in limiters:
                st.caption(limiters[key])

    # ---- writing quality ----
    st.markdown("#### ✍️ Writing quality")
    w = ats.writing
    if w is None:
        st.caption("Writing checks unavailable.")
        return
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        if w.spelling_issues:
            for i in w.spelling_issues[:14]:
                st.markdown(components.issue_row(i.kind, i.message, i.suggestion, i.context),
                            unsafe_allow_html=True)
        else:
            st.success("No common misspellings detected (rule-based dictionary).")
        if w.long_sentences:
            st.warning(f"📝 {len(w.long_sentences)} sentence(s) exceed 34 words — split them "
                       "into crisp bullets.")
            for s in w.long_sentences[:4]:
                st.markdown(f"<div style='color:{styles.C['muted']};font-size:12.5px;font-style:italic'>"
                            f"“{components.esc(s[:220])}…”</div>", unsafe_allow_html=True)
    with col_b:
        if w.weak_phrasings:
            for i in w.weak_phrasings[:10]:
                st.markdown(components.issue_row(i.kind, i.message, i.suggestion, i.context),
                            unsafe_allow_html=True)
        else:
            st.success("No weak verb phrases detected.")
        if w.buzzwords_found:
            st.warning("🪄 Buzzwords: " + ", ".join(w.buzzwords_found))
        if w.repeated_words:
            st.caption("⏱ Repeated terms (6+ occurrences): " +
                       ", ".join(f"{word} ×{cnt}" for word, cnt in w.repeated_words[:6]))

    # ---- contact & structure ----
    st.markdown("#### 🔎 What we extracted (verified)")
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown("**Contact details**")
        contacto = [
            ("Email", parsed.contact.get("email") or "—"),
            ("Phone", parsed.contact.get("phone") or "—"),
            ("LinkedIn", parsed.contact.get("linkedin") or "—"),
            ("Links found", str(len(parsed.links))),
        ]
        st.markdown("<div style='font-size:13.5px;line-height:2;'>" +
                    "".join(f"<div><b>{k}:</b> {components.esc(v)}</div>" for k, v in contacto) +
                    "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("**Document stats**")
        det = [("Pages", str(parsed.pages if parsed.pages else "—")),
               ("Words", str(parsed.word_count)),
               ("Bullets", str(parsed.bullet_count)),
               ("Tables detected", str(parsed.tables_detected)),
               ("Images detected", str(parsed.images_detected if parsed.file_type == 'pdf' else 'n/a'))]
        st.markdown("<div style='font-size:13.5px;line-height:2;'>" +
                    "".join(f"<div><b>{k}:</b> {components.esc(v)}</div>" for k, v in det) +
                    "</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("**Sections recognised** (pattern-matched, heuristic)")
        order = " → ".join(parsed.section_order) if parsed.section_order else "none detected"
        st.markdown(f"<div style='font-size:13px;line-height:1.9'>{components.esc(order)}</div>",
                    unsafe_allow_html=True)

    if parsed.warnings:
        for warn in parsed.warnings:
            st.warning(f"⚠️ {warn}", icon="⚠️")

    # ---- job match section ----
    if match:
        st.markdown("#### 🎯 Job description match")
        _job_match_inline(match)

    st.divider()
    st.markdown(f"<div style='color:{styles.C['muted']};font-size:12px;'>"
                "ℹ️ Score types — <b>Verified:</b> facts read directly from your document. "
                "<b>Heuristic:</b> pattern-based warnings that may need human judgment. "
                "The overall figure is an <b>estimated ATS compatibility score</b>, not an "
                "official ATS vendor result.</div>", unsafe_allow_html=True)


def _bulleted(items: list[str], glyph: str, numbered: bool = False) -> None:
    if not items:
        st.caption("Nothing notable detected.")
        return
    rows = "".join(
        f"<div style='margin:5px 0;font-size:13px;'><b style='color:{styles.C['muted']}'>"
        f"{(i + 1 if numbered else glyph)}.</b> {components.esc(it)}</div>"
        for i, it in enumerate(items))
    st.markdown(f"<div style=''>{rows}</div>", unsafe_allow_html=True)


def _job_match_inline(match) -> None:
    c = st.columns([1, 2, 2], gap="medium")
    with c[0]:
        st.markdown(f"""<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
            border-radius:16px;padding:18px;text-align:center;'>
            <div style='font-size:38px;font-weight:800;font-family:JetBrains Mono,monospace;color:#22d3ee;'>
            {match.match_score:.0f}%</div>
            <div style='color:{styles.C['muted']};font-size:12px;'>heuristic match estimate</div>
            <div style='margin-top:8px;font-size:13px;font-weight:600;'>{components.esc(match.job_title or 'Unnamed role')}</div>
        </div>""", unsafe_allow_html=True)
    with c[1]:
        st.markdown("**✅ Matching skills**")
        st.markdown(components.skill_chips(match.matching, styles.C["green"]), unsafe_allow_html=True)
        st.markdown("**🟡 Partial matches** (same domain, different term)")
        st.markdown(components.skill_chips(match.partial, styles.C["amber"]), unsafe_allow_html=True)
    with c[2]:
        st.markdown("**❌ Missing from resume**")
        st.markdown(components.skill_chips(match.missing, styles.C["red"]), unsafe_allow_html=True)
        if match.jd_extra_keywords:
            st.markdown("**JD vocabulary worth adding (truthfully):**")
            st.markdown(components.skill_chips(match.jd_extra_keywords, styles.C["accent2"]), unsafe_allow_html=True)
    for note in match.notes:
        st.caption("ℹ️ " + note)
