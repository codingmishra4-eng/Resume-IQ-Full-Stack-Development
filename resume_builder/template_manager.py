"""
15 prebuilt resume templates.

Each template is a *style definition* `ResumeTemplate` consumed by three
renderers: HTML preview (Streamlit live preview), the ReportLab PDF generator,
and the python-docx DOCX generator — so one definition drives all outputs and
stays visually consistent.

Layouts:
  single  — full-width, top contact header (ATS-safest)
  sidebar — decorative two-column layout (flagged with a compatibility notice)
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field

from resume_builder.resume_data import ResumeData

LAYOUT_SINGLE = "single"
LAYOUT_SIDEBAR = "sidebar"


@dataclass(frozen=True)
class ResumeTemplate:
    """A resumable, data-only template definition."""

    id: str
    name: str
    category: str
    description: str

    layout: str = LAYOUT_SINGLE                    # 'single' | 'sidebar'
    header: str = "line"                           # 'banner' | 'line' | 'plain' | 'side'
    accent: str = "#4f46e5"                        # primary accent (headings/lines)
    accent_2: str = "#94a3b8"                      # secondary (subtle elements)
    name_color: str = "#111827"
    heading_color: str = "#111827"
    text_color: str = "#1f2937"
    sidebar_bg: str = "#12203c"
    sidebar_text: str = "#e5e9f5"
    font_heading: str = "helvetica"                # helvetica | times | courier
    font_body: str = "helvetica"
    uppercase_headings: bool = False
    heading_rule: bool = True
    bullet: str = "•"
    name_size: float = 22.0
    body_size: float = 9.5
    section_order: list[str] = field(default_factory=lambda: [
        "summary", "experience", "education", "skills", "projects"])
    ats_friendly: bool = True
    notice: str = ""

    # ------------------------------------------------------------------ #
    def compatibility_note(self) -> str:
        return self.notice or (
            "ATS-friendly single-column layout." if self.ats_friendly
            else "Decorative layout: some ATS platforms may scramble or skip sidebar content.")


def _order(*sections: tuple[list[str], ...]) -> list[str]:
    out: list[str] = []
    for group in sections:
        for s in group:
            if s and s not in out:
                out.append(s)
    return out


FULL_ORDER = ["summary", "skills", "experience", "education",
              "projects", "certifications", "achievements", "languages", "interests"]


def build_default_templates() -> list[ResumeTemplate]:
    """All fifteen factory templates (id → unique, name → user-visible)."""
    t = lambda **kw: ResumeTemplate(**kw)          # noqa: E731  (concise definitions)
    return [
        t(id="modern-pro", name="Modern Professional", category="General",
          description="Clean single column with an elegant accent line — a safe all-rounder.",
          layout=LAYOUT_SINGLE, header="banner", accent="#4f46e5", accent_2="#c7d2fe",
          heading_color="#1e1b4b", uppercase_headings=False, bullet="•",
          section_order=_order(["summary", "experience"], ["skills", "education", "projects"],
                               ["certifications", "achievements", "languages", "interests"])),
        t(id="ats-minimal", name="Minimalist ATS-Friendly", category="ATS",
          description="Ultra-plain black-and-white layout optimised for maximum parser reliability.",
          layout=LAYOUT_SINGLE, header="plain", accent="#111827", accent_2="#9ca3af",
          font_heading="helvetica", uppercase_headings=True, heading_rule=True, bullet="-",
          section_order=FULL_ORDER[:]),
        t(id="software-dev", name="Software Developer", category="Engineering",
          description="Technical layout with monospace headings and a stack-focused skills grid.",
          layout=LAYOUT_SINGLE, header="banner", accent="#0d9488", accent_2="#99f6e4",
          name_color="#0f172a", font_heading="courier", bullet="▸",
          section_order=["summary", "skills", "experience", "projects", "education",
                         "certifications", "achievements", "languages"]),
        t(id="cs-fresher", name="Computer Science Fresher", category="Student",
          description="Projects and skills lead the page — tuned for applying without work history.",
          layout=LAYOUT_SINGLE, header="line", accent="#7c3aed", accent_2="#ddd6fe",
          bullet="•",
          section_order=["summary", "skills", "projects", "education", "experience",
                         "certifications", "achievements", "languages", "interests"]),
        t(id="college-student", name="College Student", category="Student",
          description="Compact, friendly layout highlighting coursework, societies and internships.",
          layout=LAYOUT_SINGLE, header="line", accent="#2563eb", accent_2="#bfdbfe",
          bullet="•",
          section_order=["summary", "education", "projects", "skills", "experience",
                         "certifications", "achievements", "languages", "interests"]),
        t(id="internship", name="Internship Applicant", category="Student",
          description="One-page eager-first layout: objective up top, coursework and projects next.",
          layout=LAYOUT_SINGLE, header="line", accent="#059669", accent_2="#a7f3d0",
          bullet="•",
          section_order=["summary", "education", "skills", "projects", "certifications",
                         "achievements", "languages", "interests"]),
        t(id="experienced", name="Experienced Professional", category="General",
          description="Confident senior layout with section rules and structured role history.",
          layout=LAYOUT_SINGLE, header="line", accent="#1e40af", accent_2="#93c5fd",
          uppercase_headings=True, bullet="•",
          section_order=["summary", "experience", "education", "skills",
                         "certifications", "achievements", "languages", "interests"]),
        t(id="executive", name="Corporate Executive", category="Corporate",
          description="Authoritative serif styling with muted gold accents for leadership profiles.",
          layout=LAYOUT_SINGLE, header="banner", accent="#a16207", accent_2="#fef08a",
          name_color="#1c1917", heading_color="#1c1917", font_heading="times",
          font_body="times", uppercase_headings=True, bullet="■",
          section_order=["summary", "experience", "education", "certifications",
                         "achievements", "skills", "languages", "interests"]),
        t(id="data-analyst", name="Data Analyst", category="Data",
          description="Quant-first layout that frames every bullet around measurable impact.",
          layout=LAYOUT_SINGLE, header="line", accent="#0891b2", accent_2="#a5f3fc",
          bullet="•",
          section_order=["summary", "skills", "experience", "projects", "education",
                         "certifications", "achievements", "languages"]),
        t(id="web-dev", name="Web Developer", category="Engineering",
          description="Modern stack-focused layout with links-forward contact header.",
          layout=LAYOUT_SINGLE, header="banner", accent="#0284c7", accent_2="#bae6fd",
          font_heading="courier", bullet="•",
          section_order=["summary", "skills", "experience", "projects", "education",
                         "certifications", "languages", "interests"]),
        t(id="uiux", name="UI/UX Designer", category="Design",
          description="Two-column designer layout with a colourful sidebar for skills and contact.",
          layout=LAYOUT_SIDEBAR, header="side", accent="#db2777", accent_2="#fbcfe8",
          sidebar_bg="#3b0764", name_color="#111827",
          font_heading="helvetica", bullet="●",
          ats_friendly=False,
          notice="Two-column creative layout — visually striking, but export the ATS-safe "
                 "DOCX (single-column) when applying through automated portals.",
          section_order=["summary", "experience", "projects", "education",
                         "certifications", "achievements", "languages"]),
        t(id="business-analyst", name="Business Analyst", category="Business",
          description="Structure-centric layout that foregrounds process and stakeholder wins.",
          layout=LAYOUT_SINGLE, header="line", accent="#155e75", accent_2="#a5f3fc",
          font_heading="times", uppercase_headings=False, bullet="•",
          section_order=["summary", "experience", "skills", "projects", "education",
                         "certifications", "achievements", "languages"]),
        t(id="academic", name="Academic Resume", category="Academic",
          description="Classic centered serif CV for research, teaching and graduate applications.",
          layout=LAYOUT_SINGLE, header="plain", accent="#334155", accent_2="#cbd5e1",
          name_color="#0f172a", font_heading="times", font_body="times",
          uppercase_headings=False, bullet="•",
          section_order=["summary", "education", "projects", "achievements",
                         "certifications", "skills", "languages", "interests"]),
        t(id="creative", name="Creative Professional", category="Design",
          description="Expressive coral sidebar layout for media, marketing and design roles.",
          layout=LAYOUT_SIDEBAR, header="side", accent="#ea580c", accent_2="#fed7aa",
          sidebar_bg="#1f2937", bullet="◆",
          ats_friendly=False,
          notice="Two-column creative layout — visually striking, but export the ATS-safe "
                 "DOCX (single-column) when applying through automated portals.",
          section_order=["summary", "skills", "projects", "experience", "education",
                         "certifications", "achievements", "languages"]),
        t(id="engineering", name="Engineering Professional", category="Engineering",
          description="Rigorous steel-toned layout for mechanical/civil/electrical profiles.",
          layout=LAYOUT_SINGLE, header="line", accent="#475569", accent_2="#cbd5e1",
          uppercase_headings=True, bullet="•",
          section_order=["summary", "skills", "experience", "projects", "education",
                         "certifications", "achievements", "languages"]),
    ]


class TemplateManager:
    """Registry for the fifteen templates (lookup, listing, HTML preview)."""

    def __init__(self, templates: list[ResumeTemplate] | None = None):
        self.templates = templates or build_default_templates()
        self._by_id = {tpl.id: tpl for tpl in self.templates}

    def all(self) -> list[ResumeTemplate]:
        return list(self.templates)

    def get(self, template_id: str) -> ResumeTemplate | None:
        return self._by_id.get(template_id)

    # ------------------------------------------------------------------ #
    # HTML live preview
    # ------------------------------------------------------------------ #
    def render_html(self, resume: ResumeData, template: ResumeTemplate) -> str:
        """Produce a self-contained HTML preview styled by the template."""
        if template.layout == LAYOUT_SIDEBAR:
            body = self._html_sidebar(resume, template)
        else:
            body = self._html_single(resume, template)
        font_head = self._font_stack(template, heading=True)
        font_body = self._font_stack(template, heading=False)

        # Precompute the h2 rule to keep CSS braces out of the f-string.
        h2_extras = "text-transform:uppercase;" if template.uppercase_headings else ""
        if template.heading_rule:
            h2_rule = "border-bottom:1.5px solid " + template.accent + ";"
        else:
            h2_rule = ""
        h2_css = (f"h2 {{ font-family:{font_head}; color:{template.accent}; "
                  f"font-size:11.5pt; letter-spacing:.12em; margin:16px 0 6px; "
                  f"{h2_extras} {h2_rule}}}")

        parts = [
            "<!doctype html><html><head><meta charset='utf-8'><style>",
            "  * { box-sizing: border-box; }",
            f"  body {{ margin:0; background:#e7eaf3; font-family:{font_body}; }}",
            f"  .page {{ width:210mm; min-height:296mm; margin:10px auto; background:#fff; "
            f"box-shadow:0 10px 30px rgba(15,23,42,.25); color:{template.name_color}; }}",
            h2_css,
            f"  h3 {{ font-family:{font_head}; color:{template.heading_color}; font-size:10.5pt; "
            f"margin:10px 0 1px; }}",
            f"  p {{ margin:2px 0; font-size:9.5pt; color:{template.text_color}; line-height:1.45; }}",
            "  ul { margin:3px 0 8px; padding-left:15px; }",
            f"  li {{ font-size:9.3pt; color:{template.text_color}; line-height:1.4; }}",
            "  .muted { color:#6b7280; font-size:8.8pt; }",
            f"  .chip {{ display:inline-block; background:{template.accent_2}; "
            f"color:{template.heading_color}; border-radius:10px; padding:2px 9px; "
            f"font-size:8.5pt; margin:2px 3px 2px 0; }}",
            "  .meta { color:#6b7280; font-size:9pt; margin:1px 0 4px; }",
            "</style></head><body>" + body + "</body></html>",
        ]
        return "\n".join(parts)

    # -- single-column HTML ------------------------------------------------
    _FONT_STACKS = {"helvetica": "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
                    "times": "'Georgia', 'Times New Roman', serif",
                    "courier": "'Cascadia Code', 'Consolas', monospace"}

    def _font_stack(self, template: ResumeTemplate, heading: bool) -> str:
        key = template.font_heading if heading else template.font_body
        return self._FONT_STACKS.get(key, self._FONT_STACKS["helvetica"])

    def _html_single(self, c: ResumeData, t: ResumeTemplate) -> str:
        banner = ""
        if t.header == "banner":
            banner = (f"background:linear-gradient(135deg,{t.accent_2}55, #ffffff);"
                      f"border-bottom:3px solid {t.accent};")
        elif t.header == "line":
            banner = f"border-bottom:3px solid {t.accent};"

        contacts = _html.escape("  |  ".join(c.contact_items())) or "your.email@example.com  |  +1 000 000 000"
        sections: list[str] = []
        for key in t.section_order:
            block = self._html_section(c, key, t)
            if block:
                sections.append(block)
        for extra in c.extra_sections:
            title = _html.escape(extra.get("title", ""))
            text = _html.escape(extra.get("body", "")).replace("\n", "<br/>")
            if title:
                sections.append(f"<h2>{title}</h2><p>{text}</p>")

        name = _html.escape(c.full_name) or "Your Name"
        headline = _html.escape(c.headline) or "Your Headline"
        font_head = self._font_stack(t, heading=True)
        return f"""
<div class="page" style="{banner} padding:14mm 15mm;">
  <div style="text-align:{'center' if t.header == 'banner' else 'left'};">
    <div style="font-family:{font_head}; font-weight:800; font-size:{t.name_size}pt;
                color:{t.name_color}; letter-spacing:.4px;">{name}</div>
    <div style="color:{t.accent}; font-size:10.5pt; margin-top:2px;
                {'text-transform:uppercase; letter-spacing:.18em;' if t.uppercase_headings else ''}">{headline}</div>
    <div class="muted" style="margin-top:5px;">{contacts}</div>
  </div>
  {''.join(sections)}
</div>"""

    def _html_section(self, c: ResumeData, key: str, t: ResumeTemplate) -> str:
        """One canonical section → HTML (empty string means skip)."""
        esc = _html.escape
        if key == "summary" and c.summary:
            return f"<h2>Summary</h2><p>{esc(c.summary)}</p>"
        if key == "experience" and c.experience:
            parts = []
            for e in c.experience:
                tagline = f" · {esc(e.location)}" if e.location else ""
                parts.append(
                    f"<h3>{esc(e.role)} <span class='muted'>· {esc(e.company)}{tagline}</span></h3>"
                    f"<div class='meta'>{esc(e.start)} — {esc(e.end)}</div>"
                    f"<ul>{''.join(f'<li>{esc(b)}</li>' for b in e.bullets)}</ul>")
            return "<h2>Experience</h2>" + "".join(parts)
        if key == "education" and c.education:
            parts = [f"<h3>{esc(d.degree)}</h3>"
                     f"<div class='meta'>{esc(d.institution)}{(' · ' + esc(d.location)) if d.location else ''}"
                     f" · {esc(d.start)}—{esc(d.end)}</div>"
                     + (f"<p>{esc(d.details)}</p>" if d.details else "")
                     for d in c.education]
            return "<h2>Education</h2>" + "".join(parts)
        if key == "skills" and c.skills:
            chips = "".join(f"<span class='chip'>{esc(s)}</span>" for s in c.skills)
            return f"<h2>Skills</h2><p>{chips}</p>"
        if key == "projects" and c.projects:
            parts = [f"<h3>{esc(p.name)}{(f' <span class=muted>· {esc(p.tech)}</span>' if p.tech else '')}</h3>"
                     f"<p>{esc(p.description)}</p>"
                     + (f"<div class='muted'>🔗 {esc(p.link)}</div>" if p.link else "")
                     for p in c.projects]
            return "<h2>Projects</h2>" + "".join(parts)
        if key == "certifications" and c.certifications:
            rows = [f"<h3>{esc(cert.name)}</h3>"
                    f"<div class='meta'>{esc(cert.issuer)}{(' · ' + esc(cert.year)) if cert.year else ''}</div>"
                    for cert in c.certifications]
            return "<h2>Certifications</h2>" + "".join(rows)
        if key == "achievements" and c.achievements:
            return "<h2>Achievements</h2><ul>" + "".join(f"<li>{esc(a)}</li>" for a in c.achievements) + "</ul>"
        if key == "languages" and c.languages:
            return "<h2>Languages</h2><p>" + ", ".join(
                f"{esc(l.name)} ({esc(l.level)})" for l in c.languages) + "</p>"
        if key == "interests" and c.interests:
            return "<h2>Interests</h2><p>" + esc(", ".join(c.interests)) + "</p>"
        return ""

    # -- sidebar (two-column) HTML ------------------------------------------
    def _html_sidebar(self, c: ResumeData, t: ResumeTemplate) -> str:
        esc = _html.escape
        side_bits: list[str] = []
        side_bits.append("<h2 style='color:#fff;'>Contact</h2><p style='color:" + t.sidebar_text + ";'>"
                         + "<br/>".join(esc(x) for x in c.contact_items()) + "</p>")
        if c.skills:
            chips = "".join(f"<span class='chip' style='background:{t.accent};color:#fff;'>{esc(s)}</span>"
                            for s in c.skills)
            side_bits.append(f"<h2 style='color:#fff;border:none;'>Skills</h2><p>{chips}</p>")
        if c.languages:
            side_bits.append("<h2 style='color:#fff;border:none;'>Languages</h2><p style='color:" +
                             t.sidebar_text + ";'>" +
                             "<br/>".join(esc(f"{l.name} ({l.level})") for l in c.languages) + "</p>")
        if c.interests:
            side_bits.append("<h2 style='color:#fff;border:none;'>Interests</h2><p style='color:" +
                             t.sidebar_text + ";'>" + esc(", ".join(c.interests)) + "</p>")

        main_keys = t.section_order
        main_sections = "".join(filter(None, (self._html_section(c, k, t) for k in main_keys)))
        for extra in c.extra_sections:
            title = esc(extra.get("title", ""))
            text = esc(extra.get("body", "")).replace("\n", "<br/>")
            if title:
                main_sections += f"<h2>{title}</h2><p>{text}</p>"

        name = esc(c.full_name) or "Your Name"
        headline = esc(c.headline) or "Your Headline"
        return f"""
<div class="page" style="display:flex;">
  <div style="width:64mm; background:{t.sidebar_bg}; color:{t.sidebar_text};
              padding:12mm 8mm; flex-shrink:0;">
    {''.join(side_bits)}
  </div>
  <div style="flex:1; padding:12mm 10mm;">
    <div style="font-weight:800;
                font-size:{t.name_size}pt; color:{t.name_color};">{name}</div>
    <div style="color:{t.accent}; font-size:10.5pt; margin:2px 0 10px; letter-spacing:.1em;">{headline}</div>
    <div style="border-top:3px solid {t.accent}; margin-bottom:6px;"></div>
    {main_sections}
  </div>
</div>"""


# Shared singleton for the app.
_template_manager = TemplateManager()


def get_template_manager() -> TemplateManager:
    return _template_manager
