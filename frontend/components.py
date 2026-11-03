"""
Reusable Streamlit UI components for the ResumeIQ design system.

Components here are pure presentation: they render data but never compute it.
All markup references tokens from `frontend.styles.C` and reusable CSS classes
(.ri-card, .ri-table, .ri-track …) defined in styles.BASE_CSS.
"""

from __future__ import annotations

import html as _html

from frontend.styles import C, GRADIENT_MAIN, GRADIENT_MAIN_135, esc


def _score_color(score: float) -> str:
    return C["green"] if score >= 75 else C["amber"] if score >= 50 else C["red"]


# --------------------------------------------------------------------------- #
# Score ring (circular progress, SVG + gradient stroke)
# --------------------------------------------------------------------------- #
def _ring_svg(score: float, size: int = 170, stroke: int = 11,
              sublabel: str = "") -> str:
    """Circular SVG progress gauge with a green→purple gradient stroke."""
    pct = max(0.0, min(100.0, score))
    r = (size - stroke) / 2
    cx = size / 2
    circ = 2 * 3.14159 * r
    dash = circ * pct / 100.0
    color = _score_color(score)
    uid = f"ring{abs(hash((score, size))) % 99999}"
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="ri-ring-anim"
     style="flex:none;">
  <defs>
    <linearGradient id="{uid}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{C['accent']}"/>
      <stop offset="100%" stop-color="{C['accent2']}"/>
    </linearGradient>
  </defs>
  <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="rgba(148,163,184,.14)"
          stroke-width="{stroke}"/>
  <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="url(#{uid})"
          stroke-width="{stroke}" stroke-linecap="round"
          stroke-dasharray="{dash:.1f} {circ - dash:.1f}"
          transform="rotate(-90 {cx} {cx})" class="ri-ring-fade"/>
  <text x="{cx}" y="{cx - 2}" text-anchor="middle"
        style="fill:{color};font-size:{int(size * 0.27)}px;font-weight:800;
               font-family:'JetBrains Mono',monospace;">{score:.1f}</text>
  <text x="{cx}" y="{cx + int(size * 0.16)}" text-anchor="middle"
        style="fill:{C['muted']};font-size:10px;letter-spacing:.14em;">{esc(sublabel or '/ 100')}</text>
</svg>"""


def score_ring(score: float, caption: str = "Estimated ATS score") -> None:
    """Big circular score gauge with the honest label next to it."""
    import streamlit as st
    note_color = _score_color(score)
    st.markdown(
        f"""
<div class="main-enter ri-card ri-ringcard" style="display:flex;align-items:center;gap:30px;flex-wrap:wrap;
  padding:24px 30px;">
  {_ring_svg(score, sublabel='/ 100')}
  <div style="flex:1;min-width:240px;">
    <div class="ri-eyebrow">{esc(caption)}</div>
    <div style="font-size:22px;font-weight:800;margin-top:6px;">
      {_grade(score)}</div>
    <div style="font-size:13px;color:{C['muted']};margin-top:8px;line-height:1.55;">
      Heuristic estimate computed by ResumeIQ — not certified by any ATS vendor.
      Different systems parse resumes differently.</div>
    <div style="margin-top:12px;">
      <span class="ri-badge" style="color:{note_color};background:{note_color}1e;
        border:1px solid {note_color}55;">{_grade_word(score)}</span>
    </div>
  </div>
</div>""",
        unsafe_allow_html=True)


def score_chip(score: float, label: str = "", size: int = 96) -> str:
    """Small inline circular gauge (for side panels / tables)."""
    stroke = int(size * 0.09)
    fs = int(size * 0.34)
    pct = max(0.0, min(100.0, score))
    r = (size - stroke) / 2
    cx = size / 2
    circ = 2 * 3.14159 * r
    dash = circ * pct / 100.0
    color = _score_color(score)
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="display:block;">
  <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="rgba(148,163,184,.14)" stroke-width="{stroke}"/>
  <circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}"
          stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ - dash:.1f}"
          transform="rotate(-90 {cx} {cx})"/>
  <text x="{cx}" y="{cx + fs * 0.36}" text-anchor="middle"
        style="fill:{color};font-size:{fs}px;font-weight:800;font-family:'JetBrains Mono',monospace;">{score:.0f}</text>
</svg>
<div style="text-align:center;color:{C['muted']};font-size:10.5px;margin-top:4px;">{esc(label)}</div>"""


def _grade(score: float) -> str:
    return "Good ATS readiness" if score >= 75 else "Needs polishing" if score >= 50 else "High rejection risk"


def _grade_word(score: float) -> str:
    return ("STRONG" if score >= 75 else "FAIR" if score >= 50 else "WEAK")


# --------------------------------------------------------------------------- #
# Progress bars
# --------------------------------------------------------------------------- #
def progress_bar(value: float, label: str = "", right: str = "",
                 color: str | None = None, animate: bool = True) -> str:
    """Labelled progress bar in the design system."""
    color = color or C["accent"]
    cls = " ri-fill-anim" if animate else ""
    right_html = (f"<span style='font-size:12.5px;font-weight:700;color:{color};'>"
                  f"{esc(right)}</span>" if right else "")
    label_html = (f"<span style='font-size:13px;'>{esc(label)}</span>" if label else "")
    return f"""
<div style="min-width:220px;flex:1;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
    {label_html}{right_html}
  </div>
  <div class="ri-track"><div class="ri-fill{cls}"
    style="width:{max(min(value, 100), 2):.0f}%;background:linear-gradient(90deg,{color}88,{color});"></div></div>
</div>"""


def category_bars(scores: dict[str, float]) -> str:
    """Render the six category bars as cards in a responsive grid."""
    icons = {"readability": "📖", "structure": "🧱", "completeness": "📋",
             "keywords": "🔑", "formatting": "🎯", "contact": "📞"}
    cards = []
    for name, score in scores.items():
        color = _score_color(score)
        cards.append(f"""
<div class="ri-card ri-lift" style="padding:14px 16px;min-width:250px;flex:1;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="font-size:13px;font-weight:600;">{icons.get(name, '•')} {esc(name.title())}</span>
    <span class="ri-mono" style="font-size:14px;font-weight:700;color:{color};">{score:.0f}</span>
  </div>
  <div class="ri-track"><div class="ri-fill ri-fill-anim"
    style="width:{max(score, 2):.0f}%;background:linear-gradient(90deg,{color}88,{color});"></div></div>
</div>""")
    return f"<div class='ri-flexwrap' style='margin:14px 0;'>{''.join(cards)}</div>"


# --------------------------------------------------------------------------- #
# Cards, tiles, page headers
# --------------------------------------------------------------------------- #
def stat_card(label: str, value: str, icon: str = "✨",
              tint: str | None = None) -> str:
    """KPI tile with a tinted icon chip."""
    tint = tint or C["accent"]
    return f"""
<div class="ri-stat">
  <div class="ri-stat-icon" style="background:{tint}1e;border:1px solid {tint}44;">{icon}</div>
  <div class="ri-mono" style="font-size:25px;font-weight:800;line-height:1.1;">{esc(value)}</div>
  <div class="ri-eyebrow" style="margin-top:3px;">{esc(label)}</div>
</div>"""


def page_title(title: str, subtitle: str, eyebrow: str = "") -> None:
    """Consistent page header: optional eyebrow, big title, subtitle."""
    import streamlit as st
    ey = (f"<div class='ri-eyebrow' style='margin-bottom:6px;'>{esc(eyebrow)}</div>"
          if eyebrow else "")
    st.markdown(
        f"<div class='main-enter' style='margin-bottom:18px;'>{ey}"
        f"<div class='ri-title' style='font-size:29px;'>{esc(title)}</div>"
        f"<div class='ri-subtitle' style='margin-top:4px;'>{esc(subtitle)}</div></div>",
        unsafe_allow_html=True)


def section_title(title: str, subtitle: str = "") -> None:
    """Smaller in-page heading block."""
    import streamlit as st
    sub = f"<div class='ri-subtitle'>{esc(subtitle)}</div>" if subtitle else ""
    st.markdown(f"<div style='margin:26px 0 10px;'>"
                f"<div class='ri-title'>{esc(title)}</div>{sub}</div>",
                unsafe_allow_html=True)


def action_card(icon: str, title: str, desc: str, page: str, key: str,
                tint: str | None = None) -> None:
    """Clickable quick-action tile: HTML card + invisible Streamlit trigger."""
    import streamlit as st
    tint = tint or C["accent"]
    st.markdown(f"""
<div class="ri-action">
  <div class="ri-action-icon" style="background:{tint}1e;border:1px solid {tint}44;">{icon}</div>
  <div>
    <div style="font-weight:700;font-size:14.5px;">{esc(title)}</div>
    <div style="color:{C['muted']};font-size:12.5px;margin-top:3px;line-height:1.5;">{esc(desc)}</div>
  </div>
</div>""", unsafe_allow_html=True)
    if st.button("Open  →", key=key, use_container_width=True):
        st.session_state.nav = page
        st.rerun()


# --------------------------------------------------------------------------- #
# Badges, pills, chips, findings
# --------------------------------------------------------------------------- #
def badge(text: str, color: str) -> str:
    """Uppercase status chip."""
    return (f"<span class='ri-badge' style='color:{color};background:{color}1e;"
            f"border:1px solid {color}55;'>{esc(text)}</span>")


def score_badge(score: float) -> str:
    """Score → colored STRONG/FAIR/WEAK chip."""
    color = _score_color(score)
    return badge(_grade_word(score), color)


def status_pill(status: str) -> str:
    """pass/warn/fail → colored status dot."""
    color = {"pass": C["green"], "ok": C["green"], "warn": C["amber"],
             "fail": C["red"]}.get(status, C["muted"])
    return f"<span class='ri-dot' style='background:{color};box-shadow:0 0 6px {color}66;'></span>"


def checks_table(checks: list[dict]) -> str:
    """Render a category's atomic checks as clean rows."""
    rows = []
    for ch in checks:
        detail = (f" <span style='color:{C['muted']};font-weight:400'>— {esc(ch.get('detail', ''))}</span>"
                  if ch.get("detail") else "")
        rows.append(f"""
<div style="display:flex;align-items:baseline;gap:10px;padding:8px 2px;
     border-bottom:1px dashed rgba(41,52,66,.6);">
  <span style="padding-top:3px;">{status_pill(ch['status'])}</span>
  <div style="font-size:13.5px;"><b style="font-weight:600">{esc(ch['label'])}</b>{detail}</div>
</div>""")
    return "".join(rows) or "<span style='color:var(--muted)'>—</span>"


def issue_row(kind: str, message: str, suggestion: str, context: str = "") -> str:
    """One spelling/grammar/weak-verb finding with evidence."""
    icon = {"spelling": "🔤", "grammar": "🧾", "weak_verb": "💪", "style": "🎨"}.get(kind, "•")
    ctx = (f"<div style='font-size:12px;color:{C['muted']};font-style:italic;margin-top:3px;'>"
           f"…{esc(context)}…</div>") if context else ""
    return f"""
<div class="ri-card" style="padding:11px 14px;margin:8px 0;">
  <div style="font-size:13.5px;font-weight:600;">{icon} {esc(message)}</div>{ctx}
  <div style="font-size:12.5px;color:{C['green']};margin-top:4px;">→ {esc(suggestion)}</div>
</div>"""


def skill_chips(skills: list[str], color: str = C['accent'], bg_alpha: str = "1e") -> str:
    """Colored skill chips (kept signature-compatible with older pages)."""
    return "".join(
        f"<span style='display:inline-block;background:{color}{bg_alpha};"
        f"border:1px solid {color}44;color:{C['text']};border-radius:99px;"
        f"padding:3px 11px;font-size:12.5px;margin:3px 4px 3px 0;'>"
        f"{esc(s)}</span>" for s in skills) or f"<span style='color:{C['muted']}'>—</span>"


def segmented_progress(value: float, label: str = "", color: str | None = None) -> str:
    """Thin inline progress bar (kept signature-compatible)."""
    return progress_bar(value, label=label, color=color, animate=True)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def data_table(headers: list[str], rows: list[list[str]]) -> str:
    """Design-system table:(headers → text, rows → ready HTML cells)."""
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in r) + "</tr>" for r in rows)
    return (f"<div class='ri-tbl-scroll'><table class='ri-table'>"
            f"<thead><tr>{thead}</tr></thead><tbody>{trs}</tbody></table></div>")


# --------------------------------------------------------------------------- #
# Empty states
# --------------------------------------------------------------------------- #
def empty_state(icon: str, title: str, note: str) -> None:
    """Friendly empty-state card (backend data decides when this shows)."""
    import streamlit as st
    st.markdown(f"""
<div class="main-enter ri-card" style="padding:34px 24px;text-align:center;">
  <div style="font-size:34px;margin-bottom:10px;filter:saturate(.8);">{icon}</div>
  <div style="font-weight:700;font-size:15.5px;">{esc(title)}</div>
  <div style="color:{C['muted']};font-size:13px;margin-top:6px;line-height:1.6;">{esc(note)}</div>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Upload hero card
# --------------------------------------------------------------------------- #
def upload_hero(extra_note: str = "") -> None:
    """Instruction card rendered above the native (restyled) uploader."""
    import streamlit as st
    note = (f"<div style='margin-top:12px;'>{esc(extra_note)}</div>" if extra_note else "")
    html = (
        f"""
<div class="main-enter ri-card" style="padding:20px 24px;margin-bottom:14px;">
  <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
    <div class="ri-action-icon" style="background:{C['accent']}1e;border:1px solid {C['accent']}44;">📄</div>
    <div style="flex:1;min-width:240px;">
      <div style="font-weight:700;">Drop your resume here — or choose a file below</div>
      <div style="color:{C['muted']};font-size:12.5px;margin-top:3px;">
        PDF & DOCX only · max 10 MB · parsed entirely on your machine{note}</div>
    </div>
    <div style="display:flex;gap:6px;">
      <span class="ri-badge" style="color:{C['highlight']};background:{C['highlight']}1a;
        border:1px solid {C['highlight']}44;">PDF</span>
      <span class="ri-badge" style="color:{C['highlight']};background:{C['highlight']}1a;
        border:1px solid {C['highlight']}44;">DOCX</span>
      <span class="ri-badge" style="color:{C['muted']};background:{C['muted']}14;
        border:1px solid {C['border']};">≤ 10 MB</span>
    </div>
  </div>
</div>"""
    )
    st.markdown(html, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Disclaimer footer (honesty guarantee)
# --------------------------------------------------------------------------- #
def disclaimer(note: str = "Scores are estimated ATS-compatibility heuristics, "
                            "not official ATS vendor results.") -> str:
    color = C["muted"]
    return (f"<div style='color:{color};font-size:11.5px;border-top:1px solid {C['border']};"
            f"padding-top:10px;margin-top:18px;'>ℹ️ {esc(note)}</div>")
