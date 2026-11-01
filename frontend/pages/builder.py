"""
Resume Builder page — 15 editable templates with live preview and downloads.

Flow: template gallery → content editor (all sections, add/remove/reorder) →
live HTML preview → PDF / DOCX download → save to history.

Key trick: every repeated item gets a stable `_uid` so widget keys follow the
*content* during reorders (avoiding Streamlit's keyed-widget stale-value trap).
"""

from __future__ import annotations

import json
import uuid

import streamlit as st
import streamlit.components.v1 as components_v1

from resume_builder.builder import BuilderError, ResumeBuilder
from resume_builder.resume_data import ResumeData
from frontend import components, styles

_builder = ResumeBuilder()


def render() -> None:
    components.page_title("Resume Builder", "Choose one of 15 templates, edit every section, "
                          "watch the live preview, then export PDF or DOCX.")

    _ensure_data()
    tab_gallery, tab_editor, tab_preview = st.tabs(
        ["🗂 Template gallery", "✎ Edit content", "👁 Live preview & export"])

    with tab_gallery:
        _gallery()
    with tab_editor:
        _editor()
    with tab_preview:
        _preview_and_export(ResumeData.from_dict(st.session_state.get("resume_data") or {}))


# --------------------------------------------------------------------------- #
def _ensure_data() -> None:
    if not isinstance(st.session_state.get("resume_data"), dict):
        st.session_state["resume_data"] = {}            # None (initial state) → empty dict
    if "template_id" not in st.session_state:
        st.session_state["template_id"] = "modern-pro"


def _gallery() -> None:
    st.markdown("Pick a template — switching never loses your content. "
                "Two-column *creative* templates are flagged with an ATS compatibility note.")
    chosen = st.session_state["template_id"]

    tpls = _builder.list_templates()
    cols = st.columns(3, gap="medium")
    for idx, tpl in enumerate(tpls):
        with cols[idx % 3]:
            is_active = chosen == tpl.id
            accent = tpl.accent
            badge = "✔ ATS-SAFE" if tpl.ats_friendly else "⚠ CREATIVE"
            badge_color = styles.C["green"] if tpl.ats_friendly else styles.C["amber"]
            st.markdown(f"""
<div style='background:{styles.C['card']};border:1.5px solid {accent if is_active else styles.C['border']};
     border-radius:16px;padding:16px;'>
  <div style='display:flex;justify-content:space-between;align-items:center;'>
    <div style='width:34px;height:34px;border-radius:10px;background:{accent};
      display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;
      font-family:JetBrains Mono,monospace;'>{idx + 1}</div>
    <span style='font-size:10.5px;font-weight:700;color:{badge_color};background:{badge_color}18;
      border:1px solid {badge_color}44;border-radius:99px;padding:2px 9px;'>{badge}</span>
  </div>
  <div style='font-weight:700;margin-top:10px;'>{components.esc(tpl.name)}</div>
  <div style='color:{styles.C['muted']};font-size:12px;margin-top:4px;line-height:1.5;'>
      {components.esc(tpl.description)}</div>
  <div style='margin-top:9px;display:flex;gap:5px;'>
    <div style='width:26%;height:8px;border-radius:99px;background:{accent};'></div>
    <div style='width:44%;height:8px;border-radius:99px;background:{accent}55;'></div>
    <div style='width:30%;height:8px;border-radius:99px;background:{accent}22;'></div>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button(("✓  Selected" if is_active else "Select"),
                         key=f"tpl_{tpl.id}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state["template_id"] = tpl.id
                st.rerun()
            if not tpl.ats_friendly:
                st.caption("⚠️ " + tpl.compatibility_note())


# --------------------------------------------------------------------------- #
def _editor() -> None:
    result = dict(st.session_state["resume_data"])

    _load_import_panel()

    # -------- identity -----------------------------------------------------
    st.markdown("#### 👤 Identity & contact")
    ic1, ic2, ic3 = st.columns(3, gap="small")
    with ic1:
        result["full_name"] = st.text_input("Full name", value=result.get("full_name", ""), key="f_name")
        result["email"] = st.text_input("Email", value=result.get("email", ""), key="f_email")
    with ic2:
        result["headline"] = st.text_input("Headline (e.g. 'Data Analyst')",
                                           value=result.get("headline", ""), key="f_head")
        result["phone"] = st.text_input("Phone", value=result.get("phone", ""), key="f_phone")
    with ic3:
        result["location"] = st.text_input("Location", value=result.get("location", ""), key="f_loc")
        result["linkedin"] = st.text_input("LinkedIn", value=result.get("linkedin", ""), key="f_link")
    gl1, gl2 = st.columns(2, gap="small")
    with gl1:
        result["github"] = st.text_input("GitHub (optional)", value=result.get("github", ""), key="f_git")
    with gl2:
        result["website"] = st.text_input("Website / portfolio (optional)",
                                          value=result.get("website", ""), key="f_web")

    # -------- summary ------------------------------------------------------
    st.markdown("#### 📝 Professional summary")
    result["summary"] = st.text_area("3–4 lines · role, level, one quantified win",
                                     value=result.get("summary", ""), height=110, key="f_sum")

    # -------- main repeated sections -----------------------------------------
    result["experience"] = _multi_section(
        "💼 Work experience & internships", "experience",
        fields=[("role", "Role"), ("company", "Company"), ("location", "Location"),
                ("start", "Start (Jun 2024)"), ("end", "End / Present")],
        bullet_label="Achievement bullets — verb + real, verifiable metrics")

    result["education"] = _multi_section(
        "🎓 Education", "education",
        fields=[("degree", "Degree"), ("institution", "Institution"), ("location", "Location"),
                ("start", "Start year"), ("end", "End year")],
        details_label="Details (CGPA, coursework, honours)")

    st.markdown("#### 🛠 Skills")
    skills_text = st.text_input("Comma-separated", value=", ".join(result.get("skills") or []),
                                key="f_skills")
    result["skills"] = [s.strip() for s in skills_text.split(",") if s.strip()]

    result["projects"] = _multi_section(
        "🚀 Projects", "projects",
        fields=[("name", "Project name"), ("tech", "Tech / tools")],
        description_label="What it does & the outcome",
        link_field=("link", "Link (GitHub / demo)"))

    result["certifications"] = _multi_section(
        "📜 Certifications", "certifications",
        fields=[("name", "Certification"), ("issuer", "Issuer"), ("year", "Year")])

    result["achievements"] = _list_section("🏆 Achievements", "achievements", joined_by="\n")
    result["languages"] = _multi_section(
        "🌐 Languages", "languages",
        fields=[("name", "Language"), ("level", "Level (Fluent…)")])

    result["interests"] = _list_section("🎨 Interests (optional)", "interests", joined_by=",")

    # -------- extra custom sections -------------------------------------------
    st.markdown("#### ➕ Extra sections")
    extras = list(result.get("extra_sections") or [])
    n_extra = st.number_input("How many custom sections?", 0, 6, len(extras), key="n_extra")
    new_extras: list[dict] = []
    for i in range(int(n_extra)):
        ex = extras[i] if i < len(extras) else {}
        ex1, ex2 = st.columns([1, 2.2])
        title = ex1.text_input("Title", value=str(ex.get("title") or ""), key=f"ext_{i}_t")
        body = ex2.text_area("Body", value=str(ex.get("body") or ""), key=f"ext_{i}_b", height=70)
        if title:
            new_extras.append({"title": title, "body": body})
    result["extra_sections"] = new_extras

    _completeness_meter(result)
    st.session_state["resume_data"] = result


def _load_import_panel() -> None:
    with st.expander("⏪ Load / import", expanded=not st.session_state["resume_data"]):
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown("**Saved resumes**")
            from database.database import get_db
            saved = get_db().list_resumes()
            if saved:
                for rec in saved:
                    cc = st.columns([2.6, 1, 1])
                    cc[0].markdown(f"🗂 **{components.esc(rec.name)}** — "
                                   f"{components.esc(rec.template_id)}", unsafe_allow_html=True)
                    if cc[1].button("Load", key=f"load_{rec.id}"):
                        data = json.loads(json.dumps(rec.data_json))          # deep copy
                        st.session_state["resume_data"] = data
                        st.session_state["template_id"] = rec.template_id
                        st.rerun()
                    if cc[2].button("Delete", key=f"del_{rec.id}"):
                        get_db().delete_resume(rec.id)
                        st.rerun()
            else:
                st.caption("Nothing saved yet — save a resume to reuse it later.")
        with c2:
            st.markdown("**Autofill with editable sample** (explore first, replace after)")
            if st.button("✨ Fill example content", use_container_width=True):
                st.session_state["resume_data"] = json.loads(json.dumps(_sample_resume_json()))
                st.rerun()
            st.caption("⚠️ Sample content is deliberately generic — replace with your real details.")


def _completeness_meter(result: dict) -> None:
    live = ResumeData.from_dict(result)
    pct, missing = live.completeness()
    st.markdown(f"#### 📈 Resume completeness — {pct}%")
    st.markdown(f"""<div style='background:{styles.C['card']};border:1px solid {styles.C['border']};
        border-radius:14px;padding:14px 18px;'>
        <div style='height:10px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden;'>
          <div style='width:{max(pct, 2)}%;height:100%;
               background:linear-gradient(90deg,{styles.C['accent']},{styles.C['accent2']});'></div>
        </div>
        <div style='font-size:12.5px;color:{styles.C['muted']};margin-top:8px;'>
          {'✅ All essential sections filled.' if pct >= 90 else
           'Still missing: ' + components.esc(', '.join(missing))}
        </div></div>""", unsafe_allow_html=True)


def _uid_of(item: dict) -> str:
    """Stable short id so widget keys follow content through reorders."""
    if not item.get("_uid"):
        item["_uid"] = uuid.uuid4().hex[:8]
    return item["_uid"]


def _multi_section(title: str, key: str, fields: list[tuple[str, str]],
                   bullet_label: str | None = None, details_label: str | None = None,
                   description_label: str | None = None,
                   link_field: tuple[str, str] | None = None) -> list[dict]:
    """Repeated-section editor with add / remove / reorder, backed by session."""
    st.markdown(f"#### {title}")
    items: list[dict] = [dict(it) for it in (st.session_state["resume_data"].get(key) or [])]

    def _commit(new_items: list[dict]) -> None:
        st.session_state["resume_data"][key] = new_items

    if items:
        st.caption(f"{len(items)} entr{'ies' if len(items) != 1 else 'y'} — "
                   f"▲/▼ reorder · ✕ remove · order isn't bound to input values")
    out: list[dict] = []
    n_cols = min(max(len(fields), 1), 3)
    for i, item in enumerate(items):
        uid = _uid_of(item)
        with st.container(border=True):
            ctrl1, ctrl2, ctrl3 = st.columns([0.5, 0.5, 1.6])
            if ctrl1.button("▲", key=f"{key}_up_{uid}") and i > 0:
                items[i - 1], items[i] = items[i], items[i - 1]
                _commit(items)
                st.rerun()
            if ctrl2.button("▼", key=f"{key}_dn_{uid}") and i < len(items) - 1:
                items[i], items[i + 1] = items[i + 1], items[i]
                _commit(items)
                st.rerun()
            if ctrl3.button("✕  Remove", key=f"{key}_rm_{uid}"):
                _commit([needle for j, needle in enumerate(items) if j != i])
                st.rerun()

            cols = st.columns(n_cols)
            new_item: dict = {"_uid": uid}
            for idx, (fname, flabel) in enumerate(fields):
                col = cols[idx % n_cols]
                new_item[fname] = col.text_input(f"{flabel} · #{i + 1}",
                                                 value=str(item.get(fname) or ""),
                                                 key=f"{key}_{fname}_{uid}")
            if details_label:
                new_item["details"] = st.text_input(details_label, value=str(item.get("details") or ""),
                                                    key=f"{key}_det_{uid}")
            if description_label:
                new_item["description"] = st.text_area(description_label,
                                                       value=str(item.get("description") or ""),
                                                       key=f"{key}_desc_{uid}", height=70)
            if link_field:
                lk, lk_label = link_field
                new_item[lk] = st.text_input(lk_label, value=str(item.get(lk) or ""),
                                             key=f"{key}_lk_{uid}")
            if bullet_label:
                raw = st.text_area(f"{bullet_label} · entry #{i + 1}",
                                   value="\n".join(item.get("bullets") or []),
                                   key=f"{key}_bl_{uid}", height=90)
                new_item["bullets"] = [b.strip() for b in raw.splitlines() if b.strip()]
            out.append(new_item)
    if st.button(f"➕  Add entry", key=f"{key}_add", use_container_width=True):
        fresh = {f: "" for f, _ in fields}
        _uid_of(fresh)
        _commit(items + [fresh])
        st.rerun()
    return out


def _list_section(title: str, key: str, joined_by: str) -> list[str]:
    """Simple list editing (achievements = one per line; interests = comma list)."""
    st.markdown(f"#### {title}")
    items = st.session_state["resume_data"].get(key) or []
    spacer = "\n" if joined_by == "\n" else ", "
    raw = st.text_area("One entry per line" if joined_by == "\n" else "Comma-separated",
                       value=spacer.join(items), key=f"lst_{key}", height=100)
    if joined_by == "\n":
        return [x.strip() for x in raw.splitlines() if x.strip()]
    return [x.strip() for x in raw.split(",") if x.strip()]


def _sample_resume_json() -> dict:
    """Neutral sample the user must replace (no fabricated achievements inside)."""
    return {
        "full_name": "Your Name", "headline": "Aspiring Software Engineer",
        "email": "you@example.com", "phone": "+91 00000 00000", "location": "Your City",
        "linkedin": "linkedin.com/in/yourhandle", "github": "github.com/yourhandle", "website": "",
        "summary": ("Write 3–4 lines: your role, your level, one real achievement with a number "
                    "you can verify — e.g. “built X that improved Y by [N%]”."),
        "skills": ["Skill 1", "Skill 2", "Skill 3", "Skill 4"],
        "experience": [{"role": "Intern", "company": "Company Name", "location": "City",
                        "start": "Jun 2025", "end": "Aug 2025",
                        "bullets": ["Replace with your real work bullet — start with a verb",
                                    "Add a measurable outcome you can defend (real %, users or time)"]}],
        "education": [{"degree": "B.Tech Computer Science", "institution": "Your University",
                       "location": "City", "start": "2022", "end": "2026",
                       "details": "CGPA 0.0 — replace with your real score"}],
        "projects": [{"name": "Project Name", "tech": "Tool A, Tool B",
                      "description": "One or two lines describing the project and its outcome.",
                      "link": "github.com/yourhandle/project"}],
        "certifications": [{"name": "Certification Name", "issuer": "Provider", "year": "2025"}],
        "achievements": ["Achievement with a measurable result, kept truthful"],
        "languages": [{"name": "English", "level": "Fluent"}, {"name": "Hindi", "level": "Native"}],
        "interests": ["Interest 1", "Interest 2"],
        "extra_sections": [],
    }


# --------------------------------------------------------------------------- #
def _preview_and_export(data: ResumeData) -> None:
    template_id = st.session_state["template_id"]
    tpl = _builder.template(template_id)
    html = _builder.preview_html(data, template_id)

    pv_col, side_col = st.columns([2.4, 1], gap="medium")
    with pv_col:
        st.markdown(f"**{components.esc(tpl.name)}** · {components.esc(tpl.category)} · "
                    f"{'✔ ATS-friendly' if tpl.ats_friendly else '⚠ creative layout'}",
                    unsafe_allow_html=True)
        if not tpl.ats_friendly:
            st.warning(tpl.compatibility_note(), icon="⚠️")
        components_v1.html(html, height=780, scrolling=True)

    with side_col:
        if not data.has_content():
            st.info("Fill in some content in the editor tab first.")
            return

        pct, _ = data.completeness()
        st.metric("Completeness", f"{pct}%")

        # real analyzer scoring on the composed resume text
        try:
            from backend.scoring_engine import ScoringEngine
            analysis = ScoringEngine().analyze_text(data.as_plain_text(), persist=False)
            score = analysis.ats.overall
            color = styles.C["green"] if score >= 75 else styles.C["amber"] \
                if score >= 50 else styles.C["red"]
            st.markdown(f"""<div style='text-align:center;background:{styles.C['card']};
                border:1px solid {styles.C['border']};border-radius:14px;padding:12px;'>
                <div style='color:{color};font-weight:800;font-family:JetBrains Mono,monospace;
                font-size:28px;'>{score:.0f}</div>
                <div style='font-size:10.5px;color:{styles.C['muted']};'>estimated ATS score</div>
            </div>""", unsafe_allow_html=True)
            tips = (analysis.ats.recommendations or [])[:3]
            for t in tips:
                st.caption("• " + t[:110])
        except Exception:                                    # noqa: BLE001
            st.caption("Score requires ≥60 words of content.")

        st.divider()
        st.markdown("### 📥 Export")
        fname_base = "".join(c if c.isalnum() or c in " _-" else "_"
                             for c in (data.full_name.strip() or "resume"))[:60]

        if st.button("⬇  Generate PDF", use_container_width=True, type="primary"):
            try:
                path = _builder.build(data, template_id, "pdf")
                with open(path, "rb") as fh:
                    st.download_button("⬇  Download PDF", fh, file_name=f"{fname_base}.pdf",
                                       mime="application/pdf", key="dl_pdf")
                st.success("PDF ready ✓ — click the download button above.")
            except BuilderError as exc:
                st.error(f"❌ {exc}")

        if st.button("⬇  Generate DOCX", use_container_width=True):
            try:
                path = _builder.build(data, template_id, "docx")
                with open(path, "rb") as fh:
                    st.download_button("⬇  Download DOCX", fh, file_name=f"{fname_base}.docx",
                                       mime="application/vnd.openxmlformats-officedocument."
                                            "wordprocessingml.document", key="dl_docx")
                st.success("DOCX ready ✓ — always exported in the ATS-safe single-column layout.")
            except BuilderError as exc:
                st.error(f"❌ {exc}")

        st.divider()
        st.markdown("### 💾 Save")
        save_name = st.text_input("Save as", value=data.full_name or "My resume", key="save_name")
        if st.button("Save to history", use_container_width=True):
            from database.database import get_db
            rid = get_db().save_resume(save_name, template_id,
                                       st.session_state.get("resume_data", {}))
            st.success(f"Saved ✓ (# {rid.id}) — reload it anytime from the editor tab.")
