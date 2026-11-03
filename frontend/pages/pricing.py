"""
Pricing / Upgrade page — shows exactly what the app actually defines today.

Honesty rules baked in:
- Free is the real current default (everything works locally).
- "Pro" is simply *enabling OpenAI narration with your own OPENAI_API_KEY*
  in `.env`. There is no payment processing, subscription, or account
  system in ResumeIQ — none is claimed here.
- "Pro Max" is a *planned hosted tier* spec sheet (referencing typical
  resume-SaaS plan structures). Its credit numbers are plan targets,
  clearly labelled as such — the local app never meters usage today.
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
  <div style="font-size:12.5px;line-height:1.7;color:{styles.C['muted']};margin-top:10px;
       border-top:1px solid {styles.C['border']};padding-top:10px;">
    About the credit numbers below: the <b>Pro Max</b> card shows plan targets for
    a <b>future hosted tier</b>. Today's desktop app does <b>not</b> meter usage —
    analyses, builder exports and history are already unlimited locally, so no
    credit is actually deducted anywhere.</div>
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

    # ---- Pro Max (planned hosted tier) — below the Pro column --------------
    st.markdown(_pro_max_card(), unsafe_allow_html=True)

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


def _pro_max_card() -> str:
    """Pro Max — planned heavy-use tier, laid out like a plan-spec sheet.

    Credit figures are *targets* for a future hosted tier (clearly labelled);
    today's local app meters nothing, so no number is enforced anywhere.
    """
    c = styles.C
    gold = "#F59E0B"
    gold_hi = "#FBBF24"

    def _tile(num: str, label: str, note: str) -> str:
        return (
            f"<div style='flex:1;min-width:150px;background:{c['card']};"
            f"border:1px solid {c['border']};border-radius:12px;padding:14px 16px;'>\n"
            f"  <div class='ri-mono' style='font-size:26px;font-weight:800;"
            f"color:{gold};'>{num}</div>\n"
            f"  <div style='font-size:12.5px;font-weight:600;margin-top:2px;'>{label}</div>\n"
            f"  <div style='font-size:11.5px;color:{c['muted']};margin-top:3px;'>{note}</div>\n"
            f"</div>")

    tiles = (
        _tile("100", "Resume-builder credits /mo",
              "Exports saved as polished, resume-ready documents")
        + _tile("60", "Full ATS analyses /mo",
                "Six-category scored reports with PDF exports")
        + _tile("40", "AI rewrite credits /mo",
                "Summary & bullet rewrites with phrasing variety")
        + _tile("30", "JD-match scans /mo",
                "Ranked skill-gap breakdown against any posting"))

    return f"""
<div style="margin-top:16px;border-radius:18px;padding:1px;
     background:linear-gradient(135deg,{gold}AA,{c['accent2']}66);">
  <div style="background:{c['card_strong']};border-radius:17px;padding:24px 26px;">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <div style="width:40px;height:40px;border-radius:12px;flex:none;
           background:linear-gradient(135deg,{gold},{gold_hi});
           display:flex;align-items:center;justify-content:center;font-size:19px;
           box-shadow:0 6px 16px rgba(245,158,11,.28);">👑</div>
      <span style="font-size:13px;font-weight:800;letter-spacing:.06em;
            background:{gold}22;color:{gold};border:1px solid {gold}55;
            border-radius:8px;padding:5px 12px;">PRO MAX PLAN</span>
      <span class="ri-badge" style="color:{c['green']};background:{c['green']}14;
            border:1px solid {c['green']}44;">every Pro feature included</span>
      <span class="ri-eyebrow" style="margin-left:auto;color:{c['muted']};">
        planned hosted tier · see notice →</span>
    </div>
    <div style="font-size:24px;font-weight:800;margin-top:16px;">Pro Max
      <span style="font-size:13px;color:{c['muted']};font-weight:500;">
      — for heavy users &amp; bulk tailoring</span></div>
    <div class="ri-flexwrap" style="margin-top:14px;">{tiles}</div>
    <hr style="border:none;border-top:1px solid {c['border']};margin:18px 0;">
    <div style="display:flex;gap:30px;flex-wrap:wrap;font-size:13px;line-height:2.0;">
      <div style="flex:1;min-width:250px;">
        <div class="ri-eyebrow" style="margin-bottom:6px;">Everything in Pro, plus</div>
        <div>✔ <b>High builder credits</b> — 4× the standard tier</div>
        <div>✔ All 15 templates incl. the Creative two-column set</div>
        <div>✔ No branding / watermark on any export</div>
        <div>✔ Unlimited section items, custom headings & colours</div>
      </div>
      <div style="flex:1;min-width:250px;">
        <div class="ri-eyebrow" style="margin-bottom:6px;">Extras</div>
        <div>✔ Multiple resume profiles (fresher · experienced · academic)</div>
        <div>✔ Version history across every export</div>
        <div>✔ Cover-letter builder using the same engine</div>
        <div style="color:{c['muted']};">• Price announced with the hosted tier —
          nothing to pay inside this build</div>
      </div>
    </div>
    <div style="font-size:11.5px;color:{c['muted']};margin-top:14px;
         border-top:1px dashed {c['border']};padding-top:10px;">
      ⚠️ Honest note: ResumeIQ today is local desktop software. The credits above
      are the <b>planned metering target</b> for a hosted version of Pro Max —
      in this build, analyses and builder exports are already unlimited and
      nothing is deducted or enforced.</div>
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
