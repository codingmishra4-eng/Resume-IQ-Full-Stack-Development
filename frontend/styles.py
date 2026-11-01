"""
ResumeIQ design system — global CSS for the premium dark theme.

Injected once for every page/rerun. Light theme is supported through
.streamlit/config.toml + the [data-theme] overrides below.
"""

from __future__ import annotations

import html as _html

# Palette tokens (single source of truth for inline styles too)
C = {
    "bg": "#0b1020",
    "bg_alt": "#0f172c",
    "card": "rgba(255,255,255,0.045)",
    "card_strong": "rgba(255,255,255,0.08)",
    "border": "rgba(148,163,184,0.18)",
    "text": "#e6ebf5",
    "muted": "#8b95ad",
    "accent": "#6d7dff",
    "accent2": "#22d3ee",
    "green": "#2dd4a7",
    "amber": "#f5b342",
    "red": "#ff6b81",
}

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

/* ---- app background ---- */
.stApp {{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(109,125,255,.14), transparent 60%),
    radial-gradient(900px 420px at -10% 10%, rgba(34,211,238,.10), transparent 55%),
    {C['bg']};
  color: {C['text']};
}}

/* ---- typography ---- */
html, body, .stApp, .stMarkdown, p, span, li, div, button, input, textarea, select, label {{
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
  letter-spacing: .01em;
  color: {C['text']};
}}
h1, h2, h3, h4 {{ font-weight: 700 !important; letter-spacing: -0.01em !important; }}
code, pre {{ font-family: 'JetBrains Mono', 'Consolas', monospace !important; }}

/* ---- sidebar ---- */
section[data-testid="stSidebar"] {{
  background: {C['bg_alt']};
  border-right: 1px solid {C['border']};
}}

/* ---- cards / containers ---- */
.block-container {{ padding-top: 1.4rem !important; max-width: 1280px !important; }}
div.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {C['border']}; }}
div.stTabs [data-baseweb="tab"] {{
  background: transparent; border-radius: 10px 10px 0 0; padding: 8px 18px;
  color: {C['muted']} !important; font-weight: 600;
}}
div.stTabs [aria-selected="true"] {{ color: {C['text']} !important; background: {C['card_strong']}; }}

/* ---- buttons ---- */
.stButton > button {{
  background: linear-gradient(135deg, rgba(109,125,255,.16), rgba(34,211,238,.10));
  color: {C['text']}; border: 1px solid {C['border']}; border-radius: 12px;
  padding: 8px 18px; font-weight: 600; transition: all .18s ease;
}}
.stButton > button:hover {{
  transform: translateY(-1px); border-color: rgba(109,125,255,.55);
  box-shadow: 0 6px 18px rgba(109,125,255,.25);
}}
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, {C['accent']}, #8a5cff);
  border: none; color: white;
}}
.stDownloadButton > button {{
  background: rgba(45,212,167,.14); border: 1px solid rgba(45,212,167,.35);
  color: {C['green']}; border-radius: 12px; font-weight: 600;
}}

/* ---- inputs ---- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox > div, .stMultiSelect > div {{
  background: rgba(255,255,255,.05) !important;
  border: 1px solid {C['border']} !important;
  border-radius: 10px !important;
  color: {C['text']} !important;
}}
.stTextArea textarea:focus, .stTextInput input:focus {{ border-color: {C['accent']} !important; }}
label {{ color: {C['muted']} !important; font-weight: 600 !important; font-size: .82rem; }}

/* ---- dataframes ---- */
div[data-testid="stDataFrame"] {{ border-radius: 12px; border: 1px solid {C['border']}; }}

/* ---- alerts ---- */
div[data-testid="stAlert"] {{ border-radius: 12px; }}

/* ---- misc ---- */
hr {{ border-color: {C['border']}; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,.25); border-radius: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}

/* fade-in for page content */
.main-enter {{ animation: fadeUp .45s ease both; }}
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

</style>
"""


def inject_base_css() -> None:
    """Apply the global theme (call once at the top of every page render)."""
    import streamlit as st
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def esc(text: str) -> str:
    return _html.escape(text or "")
