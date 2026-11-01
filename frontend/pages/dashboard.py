"""
Dashboard page — hero, stats, score trend, recent analyses, quick actions.
"""

from __future__ import annotations

import streamlit as st

import config
from database.database import get_db, record_to_dict
from frontend import components, styles


def render() -> None:
    db = get_db()
    stats = db.stats()
    trend = db.score_trend()

    components.page_title("Welcome to ResumeIQ", "Your AI resume command center — "
                          "analyze, score, match and build.")

    # ---- KPI row ---------------------------------------------------------
    kpi_html = (
        components.stat_card("Analyses run", str(stats["analyses"]), "🧪") +
        components.stat_card("Average score", f"{stats['avg_score']:g}", "📊") +
        components.stat_card("Best score", f"{stats['best_score']:g}", "🏆") +
        components.stat_card("Built resumes", str(stats["resumes"]), "🗂"))
    st.markdown(f"<div class='main-enter' style='display:flex;gap:14px;flex-wrap:wrap;'>{kpi_html}</div>",
                unsafe_allow_html=True)

    # ---- trend + quick actions ------------------------------------------
    trend_col, actions_col = st.columns([1.6, 1], gap="medium")
    with trend_col:
        st.markdown("#### Score trend")
        if len(trend) >= 2:
            _trend_chart(trend)
        elif len(trend) == 1:
            st.info("One analysis recorded so far. Analyze another version to watch the trend.")
        else:
            st.info("No analyses yet. Your ATS score history will appear here.")

    with actions_col:
        st.markdown("#### Quick actions")
        for label, page, icon in [
            ("Analyze a resume", "Analyze", "🧪"),
            ("Match against a job description", "Job Match", "🎯"),
            ("Improve with AI suggestions", "AI Improve", "✨"),
            ("Build a new resume", "Resume Builder", "🗂"),
        ]:
            if st.button(f"{icon}  {label}", key=f"qa_{page}", use_container_width=True):
                st.session_state.nav = page
                st.rerun()

    # ---- recent analyses --------------------------------------------------
    st.markdown("#### Recent analyses")
    records = db.list_analyses(limit=5)
    if not records:
        st.markdown(f"""<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
            border-radius:16px;padding:28px;text-align:center;color:{styles.C['muted']};'>
            No resumes analyzed yet — click <b>Analyze</b> to run your first one.</div>""",
                    unsafe_allow_html=True)
    else:
        rows = ""
        for rec in records:
            score = rec.ats_score
            color = (styles.C["green"] if score >= 75 else
                     styles.C["amber"] if score >= 50 else styles.C["red"])
            rows += f"""
<tr>
  <td style='padding:10px 8px;border-bottom:1px solid {styles.C['border']};font-weight:600;'>
      {components.esc(rec.file_name)}</td>
  <td style='padding:10px 8px;border-bottom:1px solid {styles.C['border']};color:{styles.C['muted']};'>
      {(rec.uploaded_at.strftime('%d %b %Y %H:%M') if rec.uploaded_at else '')}</td>
  <td style='padding:10px 8px;border-bottom:1px solid {styles.C['border']};color:{styles.C['muted']};'>
      {rec.word_count} words</td>
  <td style='padding:10px 8px;border-bottom:1px solid {styles.C['border']};font-weight:800;color:{color};'>
      {score:.1f}</td>
  <td style='padding:10px 8px;border-bottom:1px solid {styles.C['border']};'>
      {('—' if rec.job_match_score is None else f'<b>{rec.job_match_score:.0f}%</b>')}</td>
</tr>"""
        st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:13.5px;'>
  <tr style='color:{styles.C['muted']};text-transform:uppercase;font-size:11px;letter-spacing:.1em;
      border-bottom:1px solid {styles.C['border']};'>
    <th style='text-align:left;padding:6px 8px;'>File</th>
    <th style='text-align:left;padding:6px 8px;'>When</th>
    <th style='text-align:left;padding:6px 8px;'>Size</th>
    <th style='text-align:left;padding:6px 8px;'>ATS score</th>
    <th style='text-align:left;padding:6px 8px;'>Job match</th>
  </tr>{rows}</table>""", unsafe_allow_html=True)

    # ---- builder teaser ----------------------------------------------------
    st.markdown("#### Resume builder")
    st.markdown(f"""<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
        border-radius:16px;padding:20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;'>
        <div style='font-size:30px;'>🗂</div>
        <div style='flex:1;min-width:220px;'>
            <div style='font-weight:700;'>15 professional templates, live preview, PDF & DOCX export</div>
            <div style='color:{styles.C['muted']};font-size:13px;margin-top:4px;'>
                Switch templates freely — your content never resets. ATS-friendly layouts flagged in the gallery.</div>
        </div>
        <div style='color:{styles.C['muted']};font-size:13px;'>{stats['resumes']} saved</div>
    </div>""", unsafe_allow_html=True)


def _trend_chart(trend: list[tuple[str, float]]) -> None:
    """Small inline SVG line chart (no external dependency)."""
    import html as _html
    width, height, pad = 640, 220, 42
    n = len(trend)
    vals = [v for _, v in trend]
    lo, hi = min(min(vals), 20), max(max(vals), 80)
    span = max(hi - lo, 1)

    def xy(i: int, v: float) -> tuple[float, float]:
        x = pad + (width - 2 * pad) * (i / max(n - 1, 1))
        y = height - pad - (height - 2 * pad) * ((v - lo) / span)
        return x, y

    pts = [xy(i, v) for i, (_, v) in enumerate(trend)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dots = "".join(
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.5' fill='#6d7dff' stroke='#0b1020' stroke-width='2'/>"
        for x, y in pts)
    labels = "".join(
        f"<text x='{x:.1f}' y='{height - 12}' text-anchor='middle' fill='#8b95ad' font-size='10'>"
        f"{_html.escape(d[5:] if len(d) >= 10 else d)}" "</text>"
        for d, (x, _) in zip([t[0] for t in trend], [(p[0], 0) for p in pts]))
    svg = (f"<svg viewBox='0 0 {width} {height}' style='width:100%;max-width:{width}px;'>"
           f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
           f"<stop offset='0%' stop-color='#6d7dff' stop-opacity='.35'/>"
           f"<stop offset='100%' stop-color='#6d7dff' stop-opacity='0'/></linearGradient></defs>"
           f"<polyline points='0,{height - pad} {path} {width},{height - pad}' fill='url(#g)' stroke='none'/>"
           f"<polyline points='{path}' fill='none' stroke='#6d7dff' stroke-width='2.5' "
           f"stroke-linejoin='round' stroke-linecap='round'/>"
           f"{dots}{labels}</svg>")
    st.markdown(svg, unsafe_allow_html=True)
