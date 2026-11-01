"""
Reusable Streamlit UI components (hand-built HTML, no external chart deps).

Components here are pure presentation: they render data but never compute it.
"""

from __future__ import annotations

import html as _html

from frontend.styles import C, esc


def _ring(score: float, size: int = 168) -> str:
    """Animated conic-gradient score ring (pure CSS, no JS)."""
    deg = max(0.0, min(100.0, score)) * 3.6
    color = C["green"] if score >= 75 else C["amber"] if score >= 50 else C["red"]
    return f"""
<div style="width:{size}px;height:{size}px;border-radius:50%;
  background:conic-gradient({color} {deg:.1f}deg, rgba(255,255,255,.07) 0deg);
  display:flex;align-items:center;justify-content:center; position:relative;">
<div style="width:{int(size*0.8)}px;height:{int(size*0.8)}px;border-radius:50%;
  background:#101830;display:flex;flex-direction:column;align-items:center;justify-content:center;">
  <div style="font-size:{int(size*0.24)}px;font-weight:800;color:{color};
       font-family:'JetBrains Mono',monospace;">{score:.1f}</div>
  <div style="font-size:10px;color:{C['muted']};letter-spacing:.12em;">/ 100</div>
</div></div>"""


def score_ring(score: float, caption: str = "Estimated ATS score") -> None:
    """Big circular score gauge with the honest label next to it."""
    import streamlit as st
    note_color = C['green'] if score >= 75 else C['amber'] if score >= 50 else C['red']
    st.markdown(
        f"""
<div class="main-enter" style="display:flex;align-items:center;gap:28px;flex-wrap:wrap;
  background:{C['card']};border:1px solid {C['border']};border-radius:20px;padding:22px 28px;">
  {_ring(score)}
  <div style="flex:1;min-width:230px;">
    <div style="font-size:12px;color:{C['muted']};letter-spacing:.14em;text-transform:uppercase;">{caption}</div>
    <div style="font-size:22px;font-weight:800;margin-top:6px;">
      {_grade(score)}</div>
    <div style="font-size:13px;color:{C['muted']};margin-top:8px;line-height:1.5;">
      Heuristic estimate computed by ResumeIQ — not certified by any ATS vendor.
      Different systems parse resumes differently.</div>
    <div style="margin-top:10px;display:inline-block;padding:4px 12px;border-radius:99px;
      background:{note_color}22;color:{note_color};font-weight:700;font-size:12px;">
      {_grade_word(score)}</div>
  </div>
</div>""",
        unsafe_allow_html=True)


def _grade(score: float) -> str:
    return "Good ATS readiness" if score >= 75 else "Needs polishing" if score >= 50 else "High rejection risk"


def _grade_word(score: float) -> str:
    return ("STRONG" if score >= 75 else "FAIR" if score >= 50 else "WEAK")


def category_bars(scores: dict[str, float]) -> str:
    """Render the six category bars in an inline grid."""
    icons = {"readability": "📖", "structure": "🧱", "completeness": "📋",
             "keywords": "🔑", "formatting": "🎯", "contact": "📞"}
    bars = []
    for name, score in scores.items():
        color = C["green"] if score >= 75 else C["amber"] if score >= 50 else C["red"]
        bars.append(f"""
<div style="min-width:270px;flex:1;">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
    <span style="font-size:13px;color:{C['text']};">{icons.get(name, '•')} {esc(name.title())}</span>
    <span style="font-size:13px;font-weight:700;color:{color};">{score:.0f}</span>
  </div>
  <div style="height:8px;border-radius:99px;background:rgba(255,255,255,.07);overflow:hidden;">
    <div style="width:{max(score, 1.5):.0f}%;height:100%;border-radius:99px;
         background:linear-gradient(90deg,{color}aa,{color});"></div>
  </div>
</div>""")
    return f"<div style='display:flex;gap:22px;flex-wrap:wrap;margin:14px 0;'>{''.join(bars)}</div>"


def stat_card(label: str, value: str, icon: str = "✨") -> str:
    """Compact KPI tile."""
    return f"""
<div style="background:{C['card']};border:1px solid {C['border']};border-radius:16px;
     padding:16px 18px;flex:1;min-width:150px;">
  <div style="font-size:20px;">{icon}</div>
  <div style="font-size:24px;font-weight:800;margin-top:4px;font-family:'JetBrains Mono',monospace;">{esc(value)}</div>
  <div style="font-size:11px;color:{C['muted']};letter-spacing:.1em;text-transform:uppercase;margin-top:2px;">{esc(label)}</div>
</div>"""


def page_title(title: str, subtitle: str) -> None:
    """Consistent page header with a subtle gradient accent."""
    import streamlit as st
    st.markdown(
        f"<div class='main-enter' style='margin-bottom:18px;'><div "
        f"style='font-size:30px;font-weight:800;'>{title}</div>"
        f"<div style='color:{C['muted']};margin-top:4px;'>{subtitle}</div></div>",
        unsafe_allow_html=True)


def status_pill(status: str) -> str:
    """pass/warn/fail → coloured chip."""
    style = {"pass": (C["green"], "✔"), "warn": (C["amber"], "▲"), "fail": (C["red"], "✖")}.get(
        status, (C["muted"], "•"))
    color, glyph = style
    return (f"<span style='color:{color};font-weight:700'>{glyph}</span>")


def checks_table(checks: list[dict]) -> str:
    """Render a category's atomic checks as rows."""
    rows = []
    for ch in checks:
        detail = f" <span style='color:{C['muted']}'>— {esc(ch.get('detail', ''))}</span>" \
            if ch.get("detail") else ""
        rows.append(f"<div style='padding:7px 0;border-bottom:1px dashed {C['border']};'>"
                    f"{status_pill(ch['status'])} <b style='font-size:13.5px'>{esc(ch['label'])}</b>{detail}</div>")
    return "".join(rows)


def issue_row(kind: str, message: str, suggestion: str, context: str = "") -> str:
    """One spelling/grammar/weak-verb finding with evidence."""
    icon = {"spelling": "🔤", "grammar": "🧾", "weak_verb": "💪", "style": "🎨"}.get(kind, "•")
    ctx = f"<div style='font-size:12px;color:{C['muted']};font-style:italic'>…{esc(context)}…</div>" if context else ""
    return f"""
<div style="background:{C['card']};border:1px solid {C['border']};border-radius:12px;padding:10px 14px;margin:7px 0;">
  <div style="font-size:13px;"><b>{icon} {esc(message)}</b>{ctx}</div>
  <div style="font-size:12.5px;color:{C['green']};margin-top:3px;">→ {esc(suggestion)}</div>
</div>"""


def skill_chips(skills: list[str], color: str = C['accent'], bg_alpha: str = "18") -> str:
    """Purple skill chips."""
    return "".join(
        f"<span style='display:inline-block;background:{color}{bg_alpha};border:1px solid {color}44;"
        f"color:{C['text']};border-radius:99px;padding:3px 11px;font-size:12.5px;margin:3px 4px 3px 0;'>"
        f"{esc(s)}</span>" for s in skills) or f"<span style='color:{C['muted']}'>—</span>"


def segmented_progress(value: float, label: str = "", color: str | None = None) -> str:
    color = color or C["accent"]
    return f"""
<div style="min-width:160px;">
  <div style="height:6px;background:rgba(255,255,255,.08);border-radius:99px;overflow:hidden;">
    <div style="width:{max(min(value,100),2):.0f}%;height:100%;background:{color};border-radius:99px;"></div>
  </div>
</div>"""
