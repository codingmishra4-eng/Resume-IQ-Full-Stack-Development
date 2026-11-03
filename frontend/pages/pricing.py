"""
Pricing / Upgrade page — shows exactly what the app actually defines today.

Honesty rules baked in:
- Free is the real current default (everything works locally).
- "Pro" is simply *enabling OpenAI narration with your own OPENAI_API_KEY*
  in `.env`. There is no payment processing, subscription, or account
  system in ResumeIQ — none is claimed here.
"""

from __future__ import annotations

import streamlit as st

import config
from frontend import components, styles


def render() -> None:
    components.page_title(
        "Plans & Pricing", "ResumeIQ is local-first software — here is exactly what "
        "is free today and how AI narration is unlocked.",
        eyebrow="upgrade")

    free_html, pro_html = _free_card(), _pro_card()
    plan_col, badge_col = st.columns([1, 1.15], gap="medium")

    with plan_col:
        st.markdown(f"<div class='ri-flexwrap'>{free_html}{pro_html}</div>",
                    unsafe_allow_html=True)

    with badge_col:
        # Reality check strip — no payments / no accounts exist in the app.
        st.markdown(f"""
<div class="ri-card" style="padding:18px 20px;margin-bottom:14px;">
  <div class="ri-eyebrow" style="margin-bottom:8px;">No payments · no accounts</div>
  <div style="font-size:13.5px;line-height:1.7;">
    ResumeIQ <b>does not process payments</b> and has no account system. “Pro”
    means pointing the app at an OpenAI key <b>you already own</b> — the app itself
    stays free and local. Whatever OpenAI charges for your API usage is between
    you and OpenAI.</div>
</div>""", unsafe_allow_html=True)

        env_path = config.BASE_DIR / ".env"
        has_env = env_path.exists()
        has_key = bool(_detect_key(env_path))
        if has_key:
            st.success("✅ An `OPENAI_API_KEY` is configured in your local `.env` — "
                       "AI narration is active. You're already on “Pro”.", icon="✨")
        elif has_env:
            st.warning("A `.env` file exists but no `OPENAI_API_KEY` inside — "
                       "AI narration stays off until the key is filled in.", icon="ℹ️")
        else:
            st.info("No `.env` found yet — copy `.env.example` to `.env` to enable "
                    "AI narration (rule-based mode is the current default).", icon="ℹ️")

        _env_instructions()

    # ---- what never changes across plans -----------------------------------
    st.markdown("<div style='margin:30px 0 10px;' class='ri-title'>Included in every plan</div>",
                unsafe_allow_html=True)
    st.markdown(f"""
<div class="ri-card" style="padding:18px 22px;line-height:2.0;font-size:13.5px;
     display:flex;gap:28px;flex-wrap:wrap;">
  <div style="flex:1;min-width:220px;">
    <div>🧪 Full six-category ATS analysis</div>
    <div>🎯 Job-description matching</div>
    <div>🗂 History, trends & comparisons (SQLite)</div>
  </div>
  <div style="flex:1;min-width:220px;">
    <div>🗂 Resume builder — all 15 templates</div>
    <div>📄 Unlimited PDF & DOCX exports</div>
    <div>🔒 Local-first: nothing leaves your machine except your own AI calls</div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown(f"<div style='margin-top:20px;'>{components.disclaimer()}</div>",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
def _free_card() -> str:
    c = styles.C
    return f"""
<div class="ri-card ri-lift" style="padding:22px;flex:1;min-width:280px;">
  <div class="ri-eyebrow">current default</div>
  <div style="font-size:24px;font-weight:800;margin-top:4px;">Free</div>
  <div style="font-size:34px;font-weight:800;margin-top:10px;">₹0
    <span style="font-size:13px;color:{c['muted']};font-weight:500;">
    — local software, no cost</span></div>
  <hr style="border:none;border-top:1px solid {c['border']};margin:16px 0;">
  <div style="font-size:13px;line-height:2.1;">
    <div>✔ Everything you see in the app today</div>
    <div>✔ Full ATS analysis & job matching</div>
    <div>✔ Rule-based AI Improve (deterministic, honest placeholders)</div>
    <div>✔ All 15 templates · PDF & DOCX export</div>
    <div>✔ Unlimited history on your own SQLite database</div>
  </div>
</div>"""


def _pro_card() -> str:
    c = styles.C
    return f"""
<div style="flex:1;min-width:280px;border-radius:16px;padding:1px;
     background:linear-gradient(135deg,{c['accent']}66,{c['accent2']}66);">
  <div style="background:{c['card_strong']};border-radius:15px;padding:22px;height:100%;">
    <div class="ri-eyebrow">optional · bring your own AI key</div>
    <div style="font-size:24px;font-weight:800;margin-top:4px;">Pro</div>
    <div style="font-size:34px;font-weight:800;margin-top:10px;">
      <span style="background:{styles.GRADIENT_MAIN};
        -webkit-background-clip:text;background-clip:text;color:transparent;">AI narration</span>
      <span style="font-size:13px;color:{c['muted']};font-weight:500;">
      — your key, your cost</span></div>
    <hr style="border:none;border-top:1px solid {c['border']};margin:16px 0;">
    <div style="font-size:13px;line-height:2.1;">
      <div>✨ OpenAI-powered resume summaries & rewrites</div>
      <div>✨ Smarter bullet improvement with phrasing variety</div>
      <div>✨ LLM keyword guidance (still grounded — never fabricated metrics)</div>
      <div style="color:{c['muted']};">• Everything Free has, unchanged</div>
      <div style="color:{c['muted']};">• Uses <code>OPENAI_API_KEY</code> from your local
        <code>.env</code></div>
    </div>
  </div>
</div>"""


def _env_instructions() -> None:
    """Real, actionable enablement steps (nothing to buy inside ResumeIQ)."""
    with st.expander("🔧 How to enable AI narration (Pro)", expanded=False):
        st.markdown("1. Create a `.env` file in the project root "
                    "(copy `.env.example`):")
        st.code("copy .env.example .env", language="bash")
        st.markdown("2. Put your OpenAI key in that file:")
        st.code("OPENAI_API_KEY=sk-...\nOPENAI_MODEL=gpt-4o-mini", language="bash")
        st.markdown("3. Restart ResumeIQ. The AI Improve page and analysis "
                    "narration switch from *rule-based* to *OpenAI* automatically "
                    "(badges on every suggestion show the source).")
        st.caption("The key stays in your local `.env` (git-ignored). ResumeIQ "
                   "never stores, transmits, or validates payment details.")


def _detect_key(env_path) -> bool:
    """True only if a non-empty OPENAI_API_KEY line exists in the local .env."""
    try:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY=") and len(line.split("=", 1)[1].strip()) > 8:
                return True
    except OSError:
        pass
    return False
