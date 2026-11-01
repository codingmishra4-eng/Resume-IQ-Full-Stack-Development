"""
PDF resume generation (ReportLab).

Renders a ResumeData with a given ResumeTemplate into a paginated PDF.
Two layout engines:

  single  — flowing single-column document (ATS-safest; used by all layouts
            flagged ATS-friendly)
  sidebar — two frames per page (coloured sidebar + main column) for
            'creative' templates

Only ReportLab's built-in fonts (Helvetica/Times/Courier) are used so the
generator works with zero external font files.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak,
                                PageTemplate, Paragraph, Spacer)

import config
from config import get_logger
from resume_builder.resume_data import ResumeData
from resume_builder.template_manager import LAYOUT_SIDEBAR, ResumeTemplate

logger = get_logger("pdf_generator")

PAGE_W, PAGE_H = A4
MARGIN = 15 * 2.2 * 1  # slight base margin multiplier to keep spacing pleasant


FONT_MAP = {"helvetica": "Helvetica", "times": "Times-Roman", "courier": "Courier"}
# ReportLab PostScript names are irregular: Times-Roman's bold is "Times-Bold".
BOLD_MAP = {"helvetica": "Helvetica-Bold", "times": "Times-Bold", "courier": "Courier-Bold"}


def _font(template: ResumeTemplate, bold: bool = False) -> str:
    key = template.font_heading if bold else template.font_body
    return (BOLD_MAP if bold else FONT_MAP).get(key, "Helvetica" if not bold else "Helvetica-Bold")


def _escape(text: str) -> str:
    """Escape ReportLab paragraph XML, preserving basic input."""
    import html as _html
    return _html.escape(text or "")


class ResumePDFGenerator:
    """One public method: generate(resume, template, out_path) -> Path."""

    def generate(self, resume: ResumeData, template: ResumeTemplate, out_path: str | Path) -> Path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if template.layout == LAYOUT_SIDEBAR:
            doc = self._sidebar_doc(path, template)
            story = self._sidebar_story(resume, template)
        else:
            doc = SimpleDoc(path)
            story = self._single_story(resume, template)

        doc.build(story)
        logger.info("Resume PDF generated at %s", path)
        return path

    # ------------------------------------------------------------------ #
    # single-column
    # ------------------------------------------------------------------ #
    def _single_story(self, c: ResumeData, t: ResumeTemplate) -> list:
        story: list = []

        # ---- header ----
        name = c.full_name or "Your Name"
        headline = c.headline
        name_style = ParagraphStyle("name", fontName=_font(t, bold=True),
                                    fontSize=t.name_size, leading=t.name_size * 1.1,
                                    textColor=_hex(t.name_color),
                                    alignment=TA_CENTER if t.header == "banner" else 0)
        head_style = ParagraphStyle("headline", fontName=_font(t), fontSize=10.5,
                                    leading=13, textColor=_hex(t.accent),
                                    alignment=TA_CENTER if t.header == "banner" else 0)
        contact_style = ParagraphStyle("contact", fontName=_font(t), fontSize=8.6,
                                       leading=11, textColor=colors.HexColor("#6b7280"),
                                       alignment=TA_CENTER if t.header == "banner" else 0)

        story.append(Paragraph(_escape(name), name_style))
        if headline:
            shown = headline.upper() if t.uppercase_headings else headline
            story.append(Paragraph(_escape(shown), head_style))
        contacts = "  |  ".join(c.contact_items())
        if contacts:
            story.append(Spacer(1, 2))
            story.append(Paragraph(_escape(contacts), contact_style))
        if t.header in ("banner", "line"):
            story.append(Spacer(1, 3))
        story.append(self._hr(t))
        story.append(Spacer(1, 4))

        # ---- sections ----
        for key in t.section_order:
            block = self._section_flowables(c, key, t)
            if block:
                story.extend(block)
        for extra in c.extra_sections:
            title = (extra.get("title") or "").strip()
            body = (extra.get("body") or "").strip()
            if title:
                story.append(self._section_title(t, title))
                story.append(Paragraph(_escape(body).replace("\n", "<br/>"),
                                       self._body_style(t)))
                story.append(Spacer(1, 6))

        return story

    def _section_title(self, t: ResumeTemplate, title: str) -> Paragraph:
        text = title.upper() if t.uppercase_headings else title
        return Paragraph(
            f"<font color='{t.accent}'><b>{_escape(text)}</b></font>",
            ParagraphStyle("secTitle", fontName=_font(t, bold=True),
                           fontSize=10.8, leading=13, textColor=_hex(t.heading_color),
                           spaceBefore=8, spaceAfter=3))

    def _hr(self, t: ResumeTemplate) -> object:
        """A thin ruled line in the accent colour — implemented as a table."""
        from reportlab.platypus import Table, TableStyle
        bar = Table([[""]], colWidths=[PAGE_W - 2 * 33.6], rowHeights=[2.2])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _hex(t.accent)),
                                 ("LINEBELOW", (0, 0), (-1, -1), 0.1, _hex(t.accent))]))
        return bar

    def _body_style(self, t: ResumeTemplate) -> ParagraphStyle:
        return ParagraphStyle("body", fontName=_font(t), fontSize=t.body_size,
                              leading=t.body_size * 1.42, textColor=_hex(t.text_color))

    def _section_head(self, t: ResumeTemplate, default_title: str, actual: str | None = None) -> list:
        """Section heading + optional rule; returns a small flowable list."""
        title = (actual or default_title)
        flows: list = [self._section_title(t, title)]
        if t.heading_rule:
            from reportlab.platypus import Table, TableStyle
            rule = Table([[""]], colWidths=[PAGE_W - 2 * 33.6], rowHeights=[1.1])
            rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _hex(t.accent))]))
            flows.append(rule)
            flows.append(Spacer(1, 3))
        return flows

    def _section_flowables(self, c: ResumeData, key: str, t: ResumeTemplate) -> list:
        """Canonical section → list of flowables ([] = skip when empty)."""
        esc = _escape
        flows: list = []
        body = self._body_style(t)
        bullet = t.bullet

        if key == "summary" and c.summary:
            flows += self._section_head(t, "Summary")
            flows.append(Paragraph(esc(c.summary), body))
            flows.append(Spacer(1, 6))
        elif key == "experience" and c.experience:
            flows += self._section_head(t, "Experience" if not t.uppercase_headings else "Experience")
            for e in c.experience:
                title = f"<b>{esc(e.role)}</b>" + (f" — {esc(e.company)}" if e.company else "")
                place = " · ".join(x for x in (e.location, "") if x)
                dates = f"{e.start} – {e.end}".strip(" –")
                head = Paragraph(
                    title + (f" <font color='#6b7280' size='8'>· {esc(place)}</font>" if place else ""),
                    ParagraphStyle("expHead", parent=body, fontName=_font(t, bold=True),
                                   fontSize=t.body_size + 0.6, spaceBefore=5))
                flows.append(head)
                if dates:
                    flows.append(Paragraph(f"<font color='#6b7280'>{esc(dates)}</font>",
                                           ParagraphStyle("expDate", parent=body, fontSize=t.body_size - 1)))
                for b in e.bullets:
                    flows.append(Paragraph(f"{bullet}  {esc(b)}", _bullet_style(t)))
                flows.append(Spacer(1, 3))
        elif key == "education" and c.education:
            flows += self._section_head(t, "Education")
            for d in c.education:
                line = f"<b>{esc(d.degree)}</b>" + (f" — {esc(d.institution)}" if d.institution else "")
                dates = f"{d.start}–{d.end}".strip("– ")
                flows.append(Paragraph(line, ParagraphStyle("eduHead", parent=body, fontName=_font(t, bold=True))))
                meta = ", ".join(x for x in (d.location, dates) if x)
                if meta:
                    flows.append(Paragraph(f"<font color='#6b7280'>{esc(meta)}</font>",
                                           ParagraphStyle("eduMeta", parent=body, fontSize=t.body_size - 1)))
                if d.details:
                    flows.append(Paragraph(esc(d.details), body))
            flows.append(Spacer(1, 5))
        elif key == "skills" and c.skills:
            flows += self._section_head(t, "Skills")
            # Wrap in a compact paragraph; keeps single-column ATS spirit.
            flows.append(Paragraph("  ·  ".join(esc(s) for s in c.skills), body))
            flows.append(Spacer(1, 5))
        elif key == "projects" and c.projects:
            flows += self._section_head(t, "Projects")
            for p in c.projects:
                line = f"<b>{esc(p.name)}</b>" + (f" <font color='#6b7280'>· {esc(p.tech)}</font>" if p.tech else "")
                flows.append(Paragraph(line, ParagraphStyle("projHead", parent=body, fontName=_font(t, bold=True))))
                if p.description:
                    flows.append(Paragraph(esc(p.description), body))
                if p.link:
                    flows.append(Paragraph(f"<font color='#2563eb'>{esc(p.link)}</font>",
                                           ParagraphStyle("lnk", parent=body, fontSize=t.body_size - 1)))
                flows.append(Spacer(1, 3))
        elif key == "certifications" and c.certifications:
            flows += self._section_head(t, "Certifications")
            for cert in c.certifications:
                meta = ", ".join(x for x in (cert.issuer, cert.year) if x)
                flows.append(Paragraph(f"{bullet}  <b>{esc(cert.name)}</b>"
                                       + (f" <font color='#6b7280'>({esc(meta)})</font>" if meta else ""),
                                       _bullet_style(t)))
            flows.append(Spacer(1, 5))
        elif key == "achievements" and c.achievements:
            flows += self._section_head(t, "Achievements")
            for a in c.achievements:
                flows.append(Paragraph(f"{bullet}  {esc(a)}", _bullet_style(t)))
            flows.append(Spacer(1, 5))
        elif key == "languages" and c.languages:
            flows += self._section_head(t, "Languages")
            flows.append(Paragraph(", ".join(f"{esc(l.name)} ({esc(l.level)})" for l in c.languages), body))
            flows.append(Spacer(1, 5))
        elif key == "interests" and c.interests:
            flows += self._section_head(t, "Interests")
            flows.append(Paragraph(", ".join(esc(i) for i in c.interests), body))
            flows.append(Spacer(1, 5))
        return flows

    # ------------------------------------------------------------------ #
    # sidebar (two frames per page)
    # ------------------------------------------------------------------ #
    def _sidebar_doc(self, path: Path, t: ResumeTemplate) -> "SidebarDoc":
        doc = SidebarDoc(path, t)
        return doc

    def _sidebar_story(self, c: ResumeData, t: ResumeTemplate) -> list:
        """Sidebar flowables; FrameBreak separates them from main column."""
        story: list = []

        name = c.full_name or "Your Name"
        story.append(Paragraph(_escape(name),
                               ParagraphStyle("sideName", fontName=_font(t, bold=True),
                                              fontSize=t.name_size * 0.82, leading=t.name_size,
                                              textColor=colors.white, spaceAfter=4)))
        if c.headline:
            story.append(Paragraph(_escape(c.headline),
                                   ParagraphStyle("sideHead", fontName=_font(t), fontSize=9,
                                                  leading=12, textColor=_hex(t.accent_2), spaceAfter=8)))
        contacts = c.contact_items()
        if contacts:
            story.append(Paragraph("<b>Contact</b>", _sidebar_head_style()))
            story.append(Paragraph("<br/>".join(_escape(x) for x in contacts), _sidebar_body_style(t)))
        if c.skills:
            story.append(Paragraph("<b>Skills</b>", _sidebar_head_style()))
            for s in c.skills:
                story.append(Paragraph(f"{t.bullet} {escape_or(s)}", _sidebar_body_style(t)))
        if c.languages:
            story.append(Paragraph("<b>Languages</b>", _sidebar_head_style()))
            for l in c.languages:
                story.append(Paragraph(f"{escape_or(l.name)} ({escape_or(l.level)})",
                                       _sidebar_body_style(t)))
        if c.interests:
            story.append(Paragraph("<b>Interests</b>", _sidebar_head_style()))
            story.append(Paragraph(", ".join(escape_or(i) for i in c.interests),
                                   _sidebar_body_style(t)))

        story.append(FrameBreak())

        # main column: reuse single-column section rendering
        main: list = []
        for key in t.section_order:
            if key in ("skills", "languages", "interests"):
                continue                                     # already in sidebar
            block = self._section_flowables(c, key, t)
            if block:
                main.extend(block)
        for extra in c.extra_sections:
            title = (extra.get("title") or "").strip()
            if title:
                main.append(self._section_title(t, title))
                main.append(Paragraph(_escape((extra.get("body") or "")).replace("\n", "<br/>"),
                                      self._body_style(t)))
                main.append(Spacer(1, 6))
        story.extend(main)

        if not any(fl is not None for fl in main):            # guard: at least something in main
            story.append(Paragraph("Start filling sections to see your resume preview.",
                                   _sidebar_body_style(t)))
        return story


def escape_or(text: str) -> str:
    import html as _html
    return _html.escape(text or "")


def _bullet_style(t: ResumeTemplate) -> ParagraphStyle:
    return ParagraphStyle("bullet", fontName=_font(t), fontSize=t.body_size,
                          leading=t.body_size * 1.38, textColor=_hex(t.text_color),
                          leftIndent=6, firstLineIndent=-6, spaceAfter=2)


def _sidebar_head_style() -> ParagraphStyle:
    return ParagraphStyle("sideHead", fontName=_font(build_default_fonts_ref(), bold=True),
                          fontSize=9.5, textColor=colors.white, spaceBefore=8, spaceAfter=3)


def build_default_fonts_ref() -> ResumeTemplate:
    """A neutral template used only to resolve fonts inside style helpers."""
    return ResumeTemplate(id="__ref__", name="ref", category="", description="")


def _sidebar_body_style(t: ResumeTemplate) -> ParagraphStyle:
    return ParagraphStyle("sideBody", fontName=_font(t), fontSize=8.8, leading=12.6,
                          textColor=colors.HexColor("#f1f5f9"), spaceAfter=2)


def _hex(value: str) -> colors.Color:
    """Parse '#rrggbb' with a safe fallback."""
    try:
        return colors.HexColor(value if value.startswith("#") else f"#{value}")
    except Exception:                                          # noqa: BLE001
        return colors.HexColor("#111827")


# ---------------------------------------------------------------------------
# SimpleDoc wrapper: single-column page with a static top band
# ---------------------------------------------------------------------------

class SimpleDoc:
    """Bound a BaseDocTemplate with a single onPage decorator for branding."""

    def __init__(self, path: Path, template: ResumeTemplate | None = None):
        from reportlab.platypus import SimpleDocTemplate
        self.doc = SimpleDocTemplate(
            str(path), pagesize=A4,
            leftMargin=15 * 2.2, rightMargin=15 * 2.2,
            topMargin=40, bottomMargin=42,
            title="Resume", author="ResumeIQ")

    def build_args(self, story: list):
        raise NotImplementedError

    def build(self, story: list) -> None:
        self.doc.build(story, onFirstPage=self._decorate, onLaterPages=self._decorate)

    def _decorate(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(_hex("#12203c"))
        canvas.rect(0, PAGE_H - 6, PAGE_W, 6, stroke=0, fill=1)
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Sidebar document: two frames per page; sidebar painted by the callback
# ---------------------------------------------------------------------------

class SidebarDoc:
    """Two-frame page template with a painted accent sidebar."""

    SIDEBAR_W = 62 * 3.0          # ~186 pt (~5% wider default for balance)

    def __init__(self, path: Path, t: ResumeTemplate):
        self.template = t
        margin = 18
        side_w = self.SIDEBAR_W
        main_w = PAGE_W - side_w - margin * 2 - 16
        self.doc = BaseDocTemplate(
            str(path), pagesize=A4, title="Resume", author="ResumeIQ")

        frame = Frame(0, 0, side_w, PAGE_H, leftPadding=18, rightPadding=12,
                      topPadding=30, bottomPadding=20, id="side", showBoundary=0)
        main = Frame(side_w + 16, 22, main_w, PAGE_H - 44, leftPadding=0,
                     rightPadding=8, topPadding=12, bottomPadding=18, id="main")
        page = PageTemplate(id="creative", frames=[frame, main],
                            onPage=self._paint_sidebar)
        self.doc.addPageTemplates([page])

    def _paint_sidebar(self, canvas, doc) -> None:
        t = self.template
        canvas.saveState()
        canvas.setFillColor(_hex(t.sidebar_bg))
        canvas.rect(0, 0, self.SIDEBAR_W, PAGE_H, stroke=0, fill=1)
        # subtle accent edge
        canvas.setFillColor(_hex(t.accent))
        canvas.rect(self.SIDEBAR_W, 0, 3, PAGE_H, stroke=0, fill=1)
        canvas.restoreState()

    def build(self, story: list) -> None:
        self.doc.build(story)
