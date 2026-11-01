"""
AI Improve page — the AI resume improvement assistant.

Works on: the last analyzed resume, a fresh upload, or pasted text.
Outputs before/after suggestions (summary rewrite, bullet improvements,
verb swaps, keyword guidance) with accept / reject / edit controls. Nothing
is applied to any stored document without an explicit user action.
"""

from __future__ import annotations

import re

import streamlit as st

from backend.ai_assistant import AIAssistant
from backend.job_matcher import JobMatcher
from backend.resume_parser import ParseError, ResumeParser
from backend.scoring_engine import ScoringEngine
from frontend import components, styles

_ai = AIAssistant()
_parser = ResumeParser()
_engine: ScoringEngine | None = None
_matcher = JobMatcher()


def render() -> None:
    global _engine
    if _engine is None:
        _engine = ScoringEngine()

    components.page_title(
        "AI Improve Assistant",
        "Before/after rewrites — accept, reject, or edit each suggestion."
        + ("" if _ai.ai_available else " *(running in rule-based mode)*"))
    if not _ai.ai_available:
        st.info("No `OPENAI_API_KEY` found — suggestions below come from ResumeIQ's "
                "**deterministic rule engine** and always use `[placeholders]` for unknown "
                "metrics. Add a key via `.env` to unlock OpenAI-powered rewrites.", icon="ℹ️")

    # ---------------- source selection -------------------------------------
    last = st.session_state.get("analysis")
    if last is not None and st.button(f"♻  Use last analyzed resume ({last.parsed.file_name})",
                                      use_container_width=True):
        # Cache the choice: a later button click runs in a *new* script run,
        # where this button will read as False again.
        st.session_state["imp_last_used"] = last.parsed.text

    file = st.file_uploader("Upload a PDF/DOCX to polish", type=["pdf", "docx"], key="imp_file")
    pasted = st.text_area("…or paste your resume text", height=140, key="imp_paste")

    text: str | None = None
    if file is not None:
        try:
            text = _parser.parse(file.getvalue(), file.name).text
        except ParseError as exc:
            st.error(f"❌ {exc}")
    if not text and pasted and pasted.strip():
        text = pasted
    if not text:
        text = st.session_state.get("imp_last_used")

    jd_text = st.text_area("Job description (optional — unlocks targeted keyword guidance)",
                           height=110, key="imp_jd")

    if st.button("✨ Suggest improvements", type="primary", key="imp_run"):
        if not text:
            st.error("Provide resume text — upload a file, paste text, or reuse the last analysis.")
        else:
            with st.spinner(("Asking OpenAI…" if _ai.ai_available else "Applying rule-based rewrites…")):
                try:
                    st.session_state["improve_bundle"] = _build_bundle(text, jd_text)
                    st.session_state["improve_text"] = text
                except ParseError as exc:
                    st.error(f"❌ {exc}")
                else:
                    st.rerun()

    if st.session_state.get("improve_bundle"):
        _render_bundle()
    else:
        _info_card()


def _build_bundle(text: str, jd_text: str) -> dict:
    """Assemble every suggestion type with provenance labels."""
    analysis = _engine.analyze_text(text, persist=False)
    resume = analysis.parsed

    bullets = [ln.strip().lstrip("•●▪·*-– ").strip() for ln in text.splitlines()
               if _looks_like_weak_bullet(ln)]

    missing: list[str] = []
    if jd_text and jd_text.strip():
        missing = _matcher.match(resume, jd_text).missing

    return {
        "ai": _ai.ai_available,
        "summary": _ai.rewrite_summary(resume.sections.get("summary", ""), text),
        "bullets": _ai.improve_bullets(bullets, text),
        "verbs": _ai.suggest_verbs(text),
        "missing": missing,
    }


def _looks_like_weak_bullet(line: str) -> bool:
    """True only for lines that genuinely read as experience bullets.

    Headers, contact lines, date ranges and title lines must never be routed
    through the rewriter — only real describable accomplishments."""
    s = line.strip()
    if not s or len(s) < 14:
        return False
    low = s.lstrip("•●▪·*-– ").lower()
    if low.startswith(("summary", "experience", "education", "skills", "projects",
                       "certifications", "achievements", "languages", "interests")):
        return False
    words = low.split()
    if len(words) < 8 or len(s) > 220:
        return False
    if any(m in low for m in ("@", "|", "linkedin.com", "github.com", "://")):
        return False
    if re.search(r"\b(?:19|20)\d{2}\b", low):        # date ranges / years
        return False
    if low.count("·") or low.count(", ") and low.count(" ") <= 6:
        return False
    from backend.grammar_checker import WEAK_PHRASES
    if any(p in low for p in WEAK_PHRASES):
        return True
    # Bullet-looking, no digit metric, no strong opening verb → worth a rewrite.
    if not re.search(r"\d", low) and not AIAssistant._is_strong_start(low):
        return True
    return False


def _info_card() -> None:
    st.markdown(f"""<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
      border-radius:18px;padding:22px;color:{styles.C['muted']};line-height:1.7;'>
      <div style='font-weight:700;color:{styles.C['text']};'>What the assistant does</div>
      <div>• Shows <b>before → after</b> comparisons; never modifies your stored files</div>
      <div>• Rewrites bullets grounded in your <b>actual content</b> — unknown metrics become
      <code>[X%]</code> placeholders you fill in with real numbers</div>
      <div>• Swaps weak phrases (“responsible for”, “worked on”) for stronger verbs</div>
      <div>• Suggests keyword weaving only for skills you actually listed</div>
    </div>""", unsafe_allow_html=True)


def _render_bundle() -> None:
    bundle = st.session_state.get("improve_bundle") or {}

    st.markdown("### 1 · Professional summary")
    summary = bundle.get("summary")
    if summary:
        _suggestion_block(summary.original, summary.improved, summary.rationale,
                          summary.source, key="summary_0",
                          empty_note="" if summary.original else
                          "No summary section was detected — the suggestion below is a starter draft.")
    else:
        st.info("Add a summary section first, then suggest improvements again.")

    st.markdown("### 2 · Weak bullet fixes")
    bullets = bundle.get("bullets") or []
    if bullets:
        for idx, sug in enumerate(bullets):
            _suggestion_block(sug.original, sug.improved, sug.rationale,
                              sug.source, key=f"bullet_{idx}")
    else:
        st.info("No weak bullets found — every suggestion source is already strong.")

    verbs = bundle.get("verbs") or []
    if verbs:
        st.markdown("### 3 · Stronger verbs & phrasing")
        for idx, sug in enumerate(verbs[:8]):
            _suggestion_block(sug.original, sug.improved, sug.rationale,
                              sug.source, key=f"verb_{idx}")

    missing = bundle.get("missing") or []
    if missing:
        st.markdown("### 4 · Closing JD skill gaps (truthfully)")
        st.markdown("Missing skills found in the JD: " +
                    components.skill_chips(missing, styles.C["red"]), unsafe_allow_html=True)
        guidance = _ai.keyword_guidance(missing, st.session_state.get("imp_jd", "") or "",
                                        st.session_state.get("improve_text", ""))
        _suggestion_block(guidance.original, guidance.improved, guidance.rationale,
                          guidance.source, key="kw_0")


def _suggestion_block(original: str, improved: str, rationale: str,
                      source: str, key: str, empty_note: str = "") -> None:
    badge = ("🤖 OpenAI" if source == "openai" else "⚙️ Rule-based")
    color = styles.C["accent2"] if source == "openai" else styles.C["amber"]
    st.markdown(f"""
<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
     border-radius:14px;padding:14px 16px;margin:10px 0;'>
  <div style='display:flex;justify-content:flex-end;margin-bottom:6px;'>
    <span style='background:{color}22;color:{color};font-size:11px;font-weight:700;
      padding:3px 10px;border-radius:99px;border:1px solid {color}55;'>{badge}</span>
  </div>
  <div style='display:grid;grid-template-columns:1fr;gap:8px;'>
    <div style='background:rgba(255,107,129,.07);border:1px solid rgba(255,107,129,.25);
      border-radius:12px;padding:10px 14px;'>
      <div style='font-size:10.5px;color:{styles.C['red']};letter-spacing:.1em;'>BEFORE</div>
      <div style='font-size:13.5px;margin-top:4px;'>{components.esc((original or '—')[:600])}</div>
    </div>
    <div style='background:rgba(45,212,167,.07);border:1px solid rgba(45,212,167,.3);
      border-radius:12px;padding:10px 14px;'>
      <div style='font-size:10.5px;color:{styles.C['green']};letter-spacing:.1em;'>AFTER</div>
      <div style='font-size:13.5px;margin-top:4px;white-space:pre-wrap;'>{components.esc((improved or '—')[:900])}</div>
    </div>
  </div>
  <div style='font-size:12px;color:{styles.C['muted']};margin-top:6px;'>{components.esc(empty_note or rationale)}</div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 2.4])
    with c1:
        accept = st.button("✔ Accept", key=f"{key}_acc")
    with c2:
        reject = st.button("✖ Reject", key=f"{key}_rej")
    with c3:
        with st.expander("✎ Edit / copy"):
            st.text_area("Edit suggestion freely (your version is what counts)", value=improved,
                         key=f"{key}_edit", height=110)
    if accept:
        st.success("Accepted ✓ — paste this version into your builder resume.")
    if reject:
        st.caption("Rejected — nothing was changed.")
