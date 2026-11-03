"""
ResumeIQ design system — global CSS for the premium dark SaaS theme.

Injected once for every page/rerun. Every color is a token in `C`; component
markup and pages must reference tokens (never hard-code hex values), so the
whole look can be re-tuned from this single file.
"""

from __future__ import annotations

import html as _html

# ---------------------------------------------------------------------------
# Palette tokens (single source of truth for inline styles too)
# ---------------------------------------------------------------------------
C = {
    # surfaces
    "bg": "#0B0F14",
    "bg_alt": "#111820",
    "card": "#161F29",
    "card_strong": "#1C2733",
    # accents
    "accent": "#10B981",      # green — primary
    "accent2": "#8B5CF6",     # purple — secondary
    "highlight": "#38BDF8",   # blue — sparingly, for links/info
    # text
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    # lines & states
    "border": "#293442",
    "green": "#10B981",
    "amber": "#F59E0B",
    "red": "#F87171",
}

# Shared gradient strings (green → purple, used sparingly)
GRADIENT_MAIN = f"linear-gradient(90deg, {C['accent']}, {C['accent2']})"
GRADIENT_MAIN_135 = f"linear-gradient(135deg, {C['accent']}, {C['accent2']})"

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

/* ---- app background: deep space with two faint accent glows ---- */
.stApp {{
  background:
    radial-gradient(1100px 520px at 10% -12%, rgba(16,185,129,.07), transparent 60%),
    radial-gradient(900px 480px at 96% -6%, rgba(139,92,246,.08), transparent 58%),
    {C['bg']};
  color: {C['text']};
}}

/* ---- typography ---- */
html, body, .stApp, .stMarkdown, p, span, li, div, button, input, textarea, select, label {{
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
  color: {C['text']};
}}
h1, h2, h3, h4 {{ font-weight: 700 !important; letter-spacing: -0.02em !important; }}
code, pre {{ font-family: 'JetBrains Mono', 'Consolas', monospace !important; }}
.block-container {{ padding-top: 1.1rem !important; max-width: 1240px !important; }}

/* ================= reusable component classes ================= */
.ri-card {{
  background: {C['card']}; border: 1px solid {C['border']}; border-radius: 16px;
}}
.ri-elevated {{
  background: {C['card_strong']}; border: 1px solid {C['border']}; border-radius: 16px;
}}
.ri-lift {{
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}}
.ri-lift:hover {{
  transform: translateY(-2px);
  border-color: rgba(16,185,129,.45);
  box-shadow: 0 10px 28px rgba(0,0,0,.35);
}}
.ri-eyebrow {{
  font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: {C['muted']};
}}
.ri-gradient-text {{
  background: {GRADIENT_MAIN};
  -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.ri-mono {{ font-family: 'JetBrains Mono', monospace; }}

/* ---- section titles inside pages ---- */
.ri-title {{
  font-size: 19px; font-weight: 800; letter-spacing: -0.01em; margin: 0 0 2px;
}}
.ri-subtitle {{ color: {C['muted']}; font-size: 13px; }}

/* ---- data tables ---- */
table.ri-table {{ width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13.5px; }}
table.ri-table th {{
  text-align: left; padding: 10px 12px; color: {C['muted']};
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em;
  border-bottom: 1px solid {C['border']};
}}
table.ri-table td {{
  padding: 11px 12px; border-bottom: 1px solid rgba(41,52,66,.55);
}}
table.ri-table tbody tr {{ transition: background .15s ease; }}
table.ri-table tbody tr:hover td {{ background: rgba(255,255,255,.025); }}
table.ri-table tbody tr:last-child td {{ border-bottom: none; }}

/* ---- progress bars (grow & shimmer once) ---- */
.ri-track {{
  height: 7px; border-radius: 99px; background: rgba(148,163,184,.13); overflow: hidden;
}}
.ri-fill {{
  height: 100%; border-radius: 99px;
}}
.ri-fill-anim {{ animation: riGrow .9s cubic-bezier(.25,.9,.35,1) both; }}
@keyframes riGrow {{ from {{ width: 0; }} }}

/* ---- badges & pills ---- */
.ri-badge {{
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 10.5px; font-weight: 700; letter-spacing: .08em;
  padding: 3px 10px; border-radius: 99px; text-transform: uppercase;
}}
.ri-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }}

/* ---- score ring choreography ---- */
.ri-ring-anim {{ animation: ringReveal 1s cubic-bezier(.3,.9,.35,1) both; }}
@keyframes ringReveal {{ from {{ opacity: 0; transform: scale(.92); }} to {{ opacity: 1; transform: scale(1); }} }}
.ri-ring-fade {{ animation: ringStroke 1.2s ease both; }}
@keyframes ringStroke {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

/* ---- stat tiles ---- */
.ri-stat {{
  background: {C['card']}; border: 1px solid {C['border']}; border-radius: 16px;
  padding: 16px 18px; flex: 1; min-width: 170px;
  transition: transform .18s ease, border-color .18s ease;
}}
.ri-stat:hover {{ transform: translateY(-2px); border-color: rgba(16,185,129,.4); }}
.ri-stat-icon {{
  width: 34px; height: 34px; border-radius: 10px; display: inline-flex;
  align-items: center; justify-content: center; font-size: 16px; margin-bottom: 10px;
}}

/* ---- quick action tiles ---- */
.ri-action {{
  background: {C['card']}; border: 1px solid {C['border']}; border-radius: 16px;
  padding: 18px; display: flex; gap: 14px; align-items: flex-start;
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}}
.ri-action:hover {{
  transform: translateY(-2px); border-color: rgba(16,185,129,.4);
  box-shadow: 0 12px 30px rgba(0,0,0,.35);
}}
.ri-action-icon {{
  width: 40px; height: 40px; border-radius: 12px; font-size: 18px; flex: none;
  display: flex; align-items: center; justify-content: center;
}}

/* ---- upload dropzone (restyled native uploader) ---- */
div[data-testid="stFileUploaderDropzone"] {{
  background: {C['card_strong']} !important;
  border: 1.5px dashed {C['border']} !important;
  border-radius: 16px !important;
  padding: 12px !important;
  transition: border-color .2s ease, background .2s ease;
}}
div[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: {C['accent']} !important;
  background: rgba(16,185,129,.05) !important;
}}
div[data-testid="stFileUploaderDropzone-react-files"] {{
  border: none !important; background: transparent !important;
}}
div[data-testid="stFileUploader"] small {{ color: {C['muted']} !important; }}

/* ---- tabs ---- */
div.stTabs [data-baseweb="tab-list"] {{
  gap: 4px; border-bottom: 1px solid {C['border']}; padding-bottom: 0;
}}
div.stTabs [data-baseweb="tab"] {{
  background: transparent; border-radius: 10px; padding: 9px 18px;
  color: {C['muted']} !important; font-weight: 600; font-size: 13.5px;
  border: 1px solid transparent;
}}
div.stTabs [data-baseweb="tab"]:hover {{ color: {C['text']} !important; background: rgba(255,255,255,.03); }}
div.stTabs [aria-selected="true"] {{
  color: {C['text']} !important;
  background: {C['card_strong']};
  border: 1px solid {C['border']};
  border-bottom: 2px solid {C['accent']};
  border-radius: 10px 10px 0 0;
}}

/* ---- buttons ---- */
.stButton > button {{
  background: {C['card_strong']}; color: {C['text']};
  border: 1px solid {C['border']}; border-radius: 12px;
  padding: 8px 18px; font-weight: 600; font-size: 13.5px;
  transition: all .18s ease;
}}
.stButton > button:hover {{
  transform: translateY(-1px);
  border-color: rgba(16,185,129,.55);
  box-shadow: 0 6px 18px rgba(16,185,129,.18);
}}
.stButton > button[kind="primary"] {{
  background: {GRADIENT_MAIN_135};
  border: none; color: #071018; font-weight: 700;
  box-shadow: 0 6px 20px rgba(16,185,129,.28);
}}
.stButton > button[kind="primary"]:hover {{ box-shadow: 0 8px 26px rgba(16,185,129,.38); }}
.stButton > button[kind="secondary"] {{ background: {C['card_strong']}; }}
.stDownloadButton > button {{
  background: rgba(16,185,129,.12); border: 1px solid rgba(16,185,129,.35);
  color: {C['green']}; border-radius: 12px; font-weight: 600; transition: all .18s ease;
}}
.stDownloadButton > button:hover {{ background: rgba(16,185,129,.2); transform: translateY(-1px); }}

/* ---- inputs ---- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox > div,
.stMultiSelect > div {{
  background: {C['bg_alt']} !important;
  border: 1px solid {C['border']} !important;
  border-radius: 10px !important;
  color: {C['text']} !important;
  transition: border-color .18s ease;
}}
.stTextArea textarea, .stTextInput input {{ color: {C['text']} !important; }}
.stTextArea textarea:focus, .stTextInput input:focus {{
  border-color: {C['accent']} !important; box-shadow: 0 0 0 3px rgba(16,185,129,.12);
}}
label {{ color: {C['muted']} !important; font-weight: 600 !important; font-size: .82rem; }}

/* ---- expanders ---- */
div[data-testid="stExpander"] {{
  background: {C['card']}; border: 1px solid {C['border']} !important;
  border-radius: 14px !important; overflow: hidden;
}}
div[data-testid="stExpander"] summary {{
  padding: 10px 16px !important;
}}
div[data-testid="stExpander"] summary:hover {{ background: rgba(255,255,255,.03); }}

/* ---- dataframes / alerts / metrics ---- */
div[data-testid="stDataFrame"] {{ border-radius: 12px; border: 1px solid {C['border']}; }}
div[data-testid="stAlert"] {{
  border-radius: 12px; border: 1px solid {C['border']};
  background: {C['card']} !important; color: {C['text']} !important;
}}
div[data-testid="stMetric"] {{
  background: {C['card']}; border: 1px solid {C['border']}; border-radius: 14px;
  padding: 12px 16px;
}}

/* ---- misc ---- */
hr {{ border-color: {C['border']}; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,.25); border-radius: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
.stApp a {{ color: {C['highlight']}; }}

/* page content entrance */
.main-enter {{ animation: fadeUp .4s ease both; }}
@keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; }} }}

/* hide Streamlit chrome that clashes with the premium look */
div[data-testid="stDeployButton"], #MainMenu {{ display: none; }}
header[data-testid="stHeader"] {{ background: transparent; }}
div[data-testid="stFileUploader"] section, div[data-testid="stFileUploader"] button {{
  border-radius: 12px !important;
}}
div[data-testid="stFileUploader"] button {{ width: 100%; }}

/* ---- Material icon hardening ----
   Streamlit renders material icons as ligature text (e.g. "keyboard_arrow_right")
   inside [data-testid="stIconMaterial"]. If its @font-face rule doesn't reach those
   spans, the raw ligature words paint OVER the neighbouring label — looking like
   corrupted text. Explicitly apply the bundled icon font so ligatures always
   collapse into a single glyph, even offline. */
[data-testid="stIconMaterial"] {{
  font-family: "Material Symbols Rounded" !important;
  font-weight: normal;
  font-style: normal;
  font-size: 20px;
  line-height: 1;
  letter-spacing: normal;
  text-transform: none;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  font-feature-settings: "liga";
  -webkit-font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased;
}}

/* ---- responsive safety ----
   Never allow horizontal overflow; stack flex rows on small screens. */
.block-container {{ padding-left: 1.5rem !important; padding-right: 1.5rem !important; }}
.ri-flexwrap {{ display: flex; flex-wrap: wrap; gap: 14px; }}
@media (max-width: 900px) {{
  .ri-4col, .ri-3col {{ flex-direction: column; }}
  div[data-testid="column"] {{ min-width: 0; }}
  table.ri-table {{ font-size: 12.5px; }}
  .stApp div[data-testid="stHorizontalBlock"] {{ overflow-x: hidden; }}
}}

</style>
"""


def inject_base_css() -> None:
    """Apply the global theme (call once at the top of every page render)."""
    import streamlit as st
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def esc(text: str) -> str:
    return _html.escape(text or "")
