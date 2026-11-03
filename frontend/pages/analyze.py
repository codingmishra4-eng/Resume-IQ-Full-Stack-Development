"""
Analyze page — upload a resume (PDF/DOCX), optional job description,
run the six-category ATS analysis and explore the full report.

The scoring/persistence pipeline (`_run_analysis`) and session keys
(`analysis`, `last_report_pdf`) are untouched; this file only restyles
the presentation layer.
"""

from __future__ import annotations

import streamlit as st

import config
from backend.scoring_engine import ScoringEngine
from frontend import components, styles


def render() -> None:
    components.page_title("Resume Analyzer", "Upload a PDF or DOCX to score its estimated "
                          "ATS compatibility — everything runs on your machine.",
                          eyebrow="analyzer")

    engine = ScoringEngine()
    if not engine.ai.ai_available:
        _ai_notice()

    # ---- upload form -------------------------------------------------------
    with st.container():
        components.upload_hero()

        up_col, jd_col = st.columns([1.25, 1], gap="medium")
        with up_col:
            file = st.file_uploader("Resume file (PDF or DOCX, max 10 MB)",
                                    type=["pdf", "docx"], accept_multiple_files=False,
                                    label_visibility="collapsed")
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

    # ---- results -----------------------------------------------------------
    if st.session_state.get("analysis"):
        _render_results()


def _ai_notice() -> None:
    c = styles.C
    st.markdown(f"""
<div class="ri-card" style="padding:12px 18px;margin:-6px 0 14px;display:flex;gap:12px;
     align-items:center;border-left:3px solid {c['highlight']};">
  <div style="font-size:17px;">🤖</div>
  <div style="font-size:12.5px;line-height:1.6;color:{c['muted']};">
    OpenAI key not configured — running in <b style="color:{c['text']};">rule-based mode</b>.
    Every score and finding is still computed from your actual document; AI-narrated
    suggestions are simply replaced by rule-generated ones.
    See <code>.env.example</code> (<b>Upgrade</b> page) to enable AI narration.</div>
</div>""", unsafe_allow_html=True)


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
    components.section_title("Analysis results",
                             f"{components.esc(parsed.file_name)} · "
                             f"{parsed.word_count} words · analyzed locally")

    # score ring + download report (row)
    ring_col, dl_col = st.columns([2.6, 1], gap="medium")
    with ring_col:
        components.score_ring(ats.overall)
    with dl_col:
        if st.session_state.get("last_report_pdf"):
            st.markdown("<div style='height:26px;'></div>", unsafe_allow_html=True)
            with open(st.session_state.last_report_pdf, "rb") as fh:
                st.download_button("⬇  Download full PDF report", fh,
                                   file_name="resumeiq_report.pdf", mime="application/pdf",
                                   use_container_width=True)
            st.caption("The complete branded report — every finding from this session.")

    st.markdown(components.category_bars(analysis.category_scores), unsafe_allow_html=True)

    # ---- strengths / weaknesses / recommendations ---------------------------
    s1, s2, s3 = st.columns(3, gap="medium")
    _finding_card(s1, "💪 Strengths", ats.strengths, "✔", styles.C["green"])
    _finding_card(s2, "🧭 Weaknesses", ats.weaknesses, "▲", styles.C["red"])
    _finding_card(s3, "✅ Top recommendations", ats.recommendations[:6], "", styles.C["accent"],
                  numbered=True)

    # ---- category detail (expandable, verified notation) --------------------
    components.section_title("Category breakdown", "Expand a category to see every atomic "
                             "check with its evidence — pass / warning / fail.")
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

    # ---- writing quality ----------------------------------------------------
    components.section_title("✍️ Writing quality", "Rule-based language checks with "
                             "evidence — fix what frames your work poorly.")
    w = ats.writing
    if w is None:
        st.caption("Writing checks unavailable.")
        return
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown("**Spelling & length**")
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
        st.markdown("**Phrasing & vocabulary**")
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

    # ---- contact & structure ------------------------------------------------
    components.section_title("🔎 What we extracted (verified)",
                             "Facts read directly from your document — shown as parsed.")
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
        order = parsed.section_order or []
        if order:
            st.markdown(components.skill_chips(order, styles.C["highlight"], "14"),
                        unsafe_allow_html=True)
        else:
            st.caption("none detected")

    if parsed.warnings:
        for warn in parsed.warnings:
            st.warning(f"⚠️ {warn}", icon="⚠️")

    # ---- job match section --------------------------------------------------
    if match:
        components.section_title("🎯 Job description match",
                                 "Computed because you supplied a JD — heuristic estimate.")
        _job_match_inline(match)


def _finding_card(col, title: str, items: list[str], glyph: str,
                  color: str, numbered: bool = False) -> None:
    """One strengths/weaknesses/recommendations card in the design system."""
    with col:
        if not items:
            st.markdown(
                f"<div class='ri-card' style='padding:14px 18px;'>"
                f"<div class='ri-eyebrow'>{components.esc(title.upper())}</div>"
                f"<div style='color:{styles.C['muted']};font-size:13px;margin-top:8px;'>"
                f"Nothing notable detected.</div></div>", unsafe_allow_html=True)
            return
        rows = "".join(
            f"<div style='display:flex;gap:9px;padding:7px 0;"
            f"border-bottom:1px dashed rgba(41,52,66,.6);'>"
            f"<span style='color:{color};font-weight:700;font-size:12.5px;flex:none;"
            f"padding-top:1px;'>{(str(i + 1) + '.') if numbered else glyph}</span>"
            f"<span style='font-size:13px;line-height:1.55;'>{components.esc(it)}</span></div>"
            for i, it in enumerate(items))
        st.markdown(
            f"<div class='ri-card' style='padding:14px 18px;'>"
            f"<div class='ri-eyebrow'>{components.esc(title.upper())}</div>"
            f"<div style='margin-top:6px;'>{rows}</div></div>", unsafe_allow_html=True)


def _job_match_inline(match) -> None:
    c = styles.C
    score_color = styles.C["green"] if match.match_score >= 75 else \
        styles.C["amber"] if match.match_score >= 50 else styles.C["red"]
    dial_col, left_col, right_col = st.columns([1, 1.5, 1.5], gap="medium")
    with dial_col:
        st.markdown(f"""
<div class="ri-card" style="padding:18px;text-align:center;">
  <div style="width:110px;height:110px;margin:0 auto;border-radius:50%;
       background:conic-gradient({score_color} {match.match_score * 3.6:.1f}deg,
       rgba(148,163,184,.14) 0deg);display:flex;align-items:center;justify-content:center;">
    <div style="width:86px;height:86px;border-radius:50%;background:{c['card']};
         display:flex;align-items:center;justify-content:center;">
      <span style="font-size:24px;font-weight:800;color:{score_color};
            font-family:'JetBrains Mono',monospace;">{match.match_score:.0f}%</span>
    </div>
  </div>
  <div class="ri-eyebrow" style="margin-top:10px;">heuristic match estimate</div>
  <div style="font-size:13.5px;font-weight:600;margin-top:3px;">
    {components.esc(match.job_title or 'Unnamed role')}</div>
</div>""", unsafe_allow_html=True)
    with left_col:
        st.markdown("**✅ Matching skills**")
        st.markdown(components.skill_chips(match.matching, styles.C["green"]), unsafe_allow_html=True)
        st.markdown("**🟡 Partial matches** (same domain, different term)")
        st.markdown(components.skill_chips(match.partial, styles.C["amber"]), unsafe_allow_html=True)
    with right_col:
        st.markdown("**❌ Missing from resume**")
        st.markdown(components.skill_chips(match.missing, styles.C["red"]), unsafe_allow_html=True)
        if match.jd_extra_keywords:
            st.markdown("**JD vocabulary worth adding (truthfully):**")
            st.markdown(components.skill_chips(match.jd_extra_keywords, styles.C["accent2"]),
                        unsafe_allow_html=True)
    for note in match.notes:
        st.caption("ℹ️ " + note)
