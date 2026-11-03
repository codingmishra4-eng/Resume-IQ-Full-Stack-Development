"""
Dashboard — greeting, live KPIs, score trend, quick actions, recent activity,
improvement overview. Every number comes from SQLite / the scoring engine.
"""

from __future__ import annotations

import datetime as _dt
import html as _html

import streamlit as st

import config
from database.database import get_db, record_to_dict
from frontend import components, styles


def render() -> None:
    db = get_db()
    stats = db.stats()
    trend = db.score_trend()

    # ---- greeting (no invented user data; time-of-day only) ----------------
    hour = _dt.datetime.now().hour
    greeting = ("Good morning" if 5 <= hour < 12 else
                "Good afternoon" if 12 <= hour < 17 else "Good evening")
    st.markdown(f"""
<div class="main-enter" style="margin-bottom:20px;">
  <div class="ri-eyebrow">{_html.escape(config.APP_NAME)} · dashboard</div>
  <div class="ri-title" style="font-size:29px;margin-top:5px;">{greeting} — your resume command center</div>
  <div class="ri-subtitle" style="margin-top:4px;">Analyze, score, match and build —
      everything stays on your device.</div>
</div>""", unsafe_allow_html=True)

    # ---- KPI row (real database values) ------------------------------------
    kpis = st.columns(4, gap="medium")
    with kpis[0]:
        st.markdown(components.stat_card("Resumes analyzed", str(stats["analyses"]), "🧪",
                                         styles.C["accent"]), unsafe_allow_html=True)
    with kpis[1]:
        st.markdown(components.stat_card("Average ATS score", f"{stats['avg_score']:g}", "📊",
                                         styles.C["highlight"]), unsafe_allow_html=True)
    with kpis[2]:
        st.markdown(components.stat_card("Best score", f"{stats['best_score']:g}", "🏆",
                                         styles.C["accent2"]), unsafe_allow_html=True)
    with kpis[3]:
        st.markdown(components.stat_card("Resumes built", str(stats["resumes"]), "🗂",
                                         styles.C["amber"]), unsafe_allow_html=True)

    # ---- trend + quick actions ---------------------------------------------
    trend_col, actions_col = st.columns([1.55, 1], gap="medium")
    with trend_col:
        st.markdown("<div style='margin:26px 0 10px;' class='ri-title'>Score trend</div>",
                    unsafe_allow_html=True)
        if len(trend) >= 2:
            _trend_chart(trend)
        elif len(trend) == 1:
            components.empty_state("📈", "One analysis recorded so far",
                                   "Analyze another version of your resume to watch the trend line here.")
        else:
            components.empty_state("📈", "No analyses yet",
                                   "Your ATS score history will appear here after your first analysis.")
    with actions_col:
        st.markdown("<div style='margin:26px 0 10px;' class='ri-title'>Quick actions</div>",
                    unsafe_allow_html=True)
        components.action_card("🧪", "Analyze a resume",
                               "Score its estimated ATS compatibility in seconds.",
                               "Analyze", "qa_analyze", styles.C["accent"])
        components.action_card("🎯", "Match against a job description",
                               "See matched, partial and missing skills.",
                               "Job Match", "qa_match", styles.C["highlight"])
        components.action_card("✨", "Improve with AI suggestions",
                               "Before/after rewrites you accept or reject.",
                               "AI Improve", "qa_improve", styles.C["accent2"])
        components.action_card("🗂", "Build a new resume",
                               "15 templates, live preview, PDF & DOCX export.",
                               "Resume Builder", "qa_builder", styles.C["amber"])

    # ---- improvement overview (real latest analysis) ------------------------
    records = db.list_analyses(limit=5)
    latest = records[0] if records else None
    st.markdown("<div style='margin:30px 0 10px;' class='ri-title'>Resume improvement overview</div>",
                unsafe_allow_html=True)
    if latest:
        rep = latest.report_json or {}
        ats = rep.get("ats", {})
        ov_col, tips_col = st.columns([1.1, 1.9], gap="medium")
        with ov_col:
            cats = {k: c.get("score", 0) for k, c in (ats.get("categories") or {}).items()}
            weakest = sorted(cats.items(), key=lambda kv: kv[1])[:2] if cats else []
            cards = "".join(
                f"<div class='ri-card' style='padding:12px 14px;flex:1;min-width:120px;'>"
                f"<div class='ri-eyebrow'>{components.esc(k)}</div>"
                f"<div class='ri-mono' style='font-size:19px;font-weight:800;"
                f"color:{_score_color(v)};margin-top:3px;'>{v:.0f}<span style='font-size:11px;"
                f"color:{styles.C['muted']};'>/100</span></div></div>"
                for k, v in weakest)
            st.markdown(f"""
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;">{cards}</div>
<div style="color:{styles.C['muted']};font-size:12px;">Lowest-scoring categories of your
 most recent analysis (#{latest.id}). Improve these first.</div>""", unsafe_allow_html=True)
        with tips_col:
            recs = (ats.get("recommendations") or [])[:3]
            if recs:
                rows = "".join(
                    f"<div style='display:flex;gap:10px;padding:8px 0;'>"
                    f"<span class='ri-dot' style='background:{styles.C['accent']};margin-top:6px;'></span>"
                    f"<div style='font-size:13.5px;line-height:1.55;'>{components.esc(t[:150])}</div></div>"
                    for t in recs)
                st.markdown(f"<div class='ri-card' style='padding:14px 18px;'>{rows}"
                            f"<div style='color:{styles.C['muted']};font-size:11.5px;margin-top:6px;'>"
                            f"Top recommendations from #{latest.id} — open "
                            f"<b>AI Improve</b> to act on them.</div></div>",
                            unsafe_allow_html=True)

    # ---- recent activity ----------------------------------------------------
    st.markdown("<div style='margin:26px 0 10px;' class='ri-title'>Recent activity</div>",
                unsafe_allow_html=True)
    if not records:
        components.empty_state("🧪", "No resumes analyzed yet",
                               "Click “Analyze a resume” above to run your first analysis — "
                               "it takes just a few seconds.")
    else:
        rows = []
        for rec in records:
            color = _score_color(rec.ats_score)
            when = rec.uploaded_at.strftime("%d %b %Y, %H:%M") if rec.uploaded_at else "—"
            match = "—" if rec.job_match_score is None else f"<b>{rec.job_match_score:.0f}%</b>"
            rows.append([
                components.esc(rec.file_name),
                f"<span style='color:{styles.C['muted']}'>{when}</span>",
                f"<span style='color:{styles.C['muted']}'>{rec.word_count} words</span>",
                f"<span class='ri-mono' style='font-weight:800;color:{color};'>{rec.ats_score:.1f}</span>",
                match,
            ])
        st.markdown(components.data_table(
            ["File", "When", "Size", "Estimated ATS score", "Job match"], rows),
            unsafe_allow_html=True)

    # ---- builder teaser -----------------------------------------------------
    st.markdown("<div style='margin:26px 0 10px;' class='ri-title'>Resume builder</div>",
                unsafe_allow_html=True)
    st.markdown(f"""
<div class="main-enter ri-card ri-lift" style="padding:20px;display:flex;gap:16px;
     align-items:center;flex-wrap:wrap;">
  <div class="ri-action-icon" style="background:{styles.C['accent2']}1e;
       border:1px solid {styles.C['accent2']}44;font-size:19px;">🗂</div>
  <div style="flex:1;min-width:230px;">
    <div style="font-weight:700;">15 professional templates · live preview · PDF & DOCX export</div>
    <div style="color:{styles.C['muted']};font-size:12.5px;margin-top:4px;">
      Switch templates freely — your content never resets. ATS-friendly layouts are flagged.</div>
  </div>
  <div style="color:{styles.C['muted']};font-size:12.5px;">{stats['resumes']} saved</div>
</div>""", unsafe_allow_html=True)


def _score_color(v: float) -> str:
    return styles.C["green"] if v >= 75 else styles.C["amber"] if v >= 50 else styles.C["red"]


def _trend_chart(trend: list[tuple[str, float]]) -> None:
    """Inline SVG line chart in the new palette (no external dependency)."""
    width, height, pad = 640, 220, 40
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
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.5' fill='{styles.C['accent']}' "
        f"stroke='{styles.C['bg_alt']}' stroke-width='2'/>" for x, y in pts)
    labels = "".join(
        f"<text x='{x:.1f}' y='{height - 12}' text-anchor='middle' "
        f"fill='{styles.C['muted']}' font-size='10' font-family='Inter,sans-serif'>"
        f"{_html.escape(d[5:] if len(d) >= 10 else d)}</text>"
        for d, (x, _) in zip([t[0] for t in trend], [(p[0], 0) for p in pts]))
    svg = f"""
<svg viewBox='0 0 {width} {height}' style='width:100%;max-width:640px;'>
  <defs>
    <linearGradient id='garea' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='{styles.C['accent']}' stop-opacity='.28'/>
      <stop offset='100%' stop-color='{styles.C['accent']}' stop-opacity='0'/>
    </linearGradient>
    <linearGradient id='gline' x1='0' y1='0' x2='1' y2='0'>
      <stop offset='0%' stop-color='{styles.C['accent']}'/>
      <stop offset='100%' stop-color='{styles.C['accent2']}'/>
    </linearGradient>
  </defs>
  <polyline points='0,{height - pad} {path} {width},{height - pad}'
    fill='url(#garea)' stroke='none'/>
  <polyline points='{path}' fill='none' stroke='url(#gline)' stroke-width='2.5'
    stroke-linejoin='round' stroke-linecap='round'/>
  {dots}{labels}
</svg>"""
    st.markdown(f"""<div class='ri-card' style='padding:18px 20px;'>{svg}</div>""",
                unsafe_allow_html=True)
