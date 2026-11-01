"""
DOCX resume generation (python-docx).

DOCX exports are always written as an ATS-safe single-column layout (Word
tables/columns are what most ATS parsers trip over). Template identity is
preserved through fonts, colours, uppercase headings and heading styling —
the user is told this in the UI when the template itself is a sidebar layout.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from config import get_logger
from resume_builder.resume_data import ResumeData
from resume_builder.template_manager import ResumeTemplate

logger = get_logger("docx_generator")

FONT_MAP = {"helvetica": "Calibri",       # Word-openable humanist default
            "times": "Georgia",           # serif look-alike kept neutral & installed everywhere
            "courier": "Consolas"}        # readable monospace on Windows


def _hex(value: str) -> RGBColor:
    raw = (value or "#111827").lstrip("#")
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raw = "111827"
    return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


class ResumeDOCXGenerator:
    """Render a resume as an editable DOCX."""

    def generate(self, resume: ResumeData, template: ResumeTemplate, out_path: str | Path) -> Path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = Document()
        self._configure_page(doc)
        font = FONT_MAP.get(template.font_body, "Calibri")

        # ---- header ------------------------------------------------------
        name = resume.full_name or "Your Name"
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if template.header == "banner" else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(name)
        run.bold, run.font.size = True, Pt(template.name_size * 0.92)
        run.font.name, run.font.color.rgb = font, _hex(template.name_color)

        if resume.headline:
            h = doc.add_paragraph()
            h.alignment = p.alignment
            r = h.add_run(resume.headline.upper() if template.uppercase_headings else resume.headline)
            r.font.size = Pt(10.5)
            r.font.color.rgb = _hex(template.accent)
            r.font.name = font

        contacts = "  |  ".join(resume.contact_items())
        if contacts:
            c = doc.add_paragraph()
            c.alignment = p.alignment
            r = c.add_run(contacts)
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
            r.font.name = font

        self._accent_rule(doc, template)

        # ---- sections (single-column, ATS-safe) ---------------------------
        for key in template.section_order:
            self._add_section(doc, resume, key, template, font)
        for extra in resume.extra_sections:
            title, body = (extra.get("title") or "").strip(), (extra.get("body") or "").strip()
            if title:
                self._heading(doc, title, template, font)
                doc.add_paragraph(body)

        doc.save(str(path))
        logger.info("Resume DOCX generated at %s", path)
        return path

    # ------------------------------------------------------------------ #
    def _configure_page(self, doc: Document) -> None:
        section = doc.sections[0]
        section.top_margin, section.bottom_margin = Pt(44), Pt(44)
        section.left_margin, section.right_margin = Pt(50), Pt(50)

    def _accent_rule(self, doc: Document, template: ResumeTemplate) -> None:
        """Thin bottom border on the header's last line (Word-safe styling)."""
        p = doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pBdr = pPr.makeelement(qn("w:pBdr"), {})
        bottom = pPr.makeelement(qn("w:bottom"), {
            qn("w:val"): "single", qn("w:sz"): "12",
            qn("w:space"): "4", qn("w:color"): template.accent.lstrip("#")})
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _heading(self, doc: Document, title: str, template: ResumeTemplate, font: str) -> None:
        text = title.upper() if template.uppercase_headings else title
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.name = font
        run.font.color.rgb = _hex(template.heading_color)

        # accent underline
        if template.heading_rule:
            pPr = p._p.get_or_add_pPr()
            pBdr = pPr.makeelement(qn("w:pBdr"), {})
            bottom = pPr.makeelement(qn("w:bottom"), {
                qn("w:val"): "single", qn("w:sz"): "6",
                qn("w:space"): "2", qn("w:color"): template.accent.lstrip("#")})
            pBdr.append(bottom)
            pPr.append(pBdr)

    def _add_section(self, doc: Document, c: ResumeData, key: str,
                     t: ResumeTemplate, font: str) -> None:
        if key == "summary" and c.summary:
            self._heading(doc, "Summary", t, font)
            doc.add_paragraph(c.summary)
        elif key == "experience" and c.experience:
            self._heading(doc, "Experience", t, font)
            for e in c.experience:
                head = " — ".join(x for x in (e.role, e.company) if x)
                p = doc.add_paragraph()
                p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(4), Pt(0)
                r = p.add_run(head)
                r.bold = True
                r.font.size = Pt(10.5)
                r.font.name = font
                meta = " · ".join(x for x in (e.location, f"{e.start} – {e.end}".strip(" –")) if x.strip(" –"))
                if meta:
                    q = doc.add_paragraph()
                    q.paragraph_format.space_after = Pt(1)
                    rr = q.add_run(meta)
                    rr.font.size, rr.font.color.rgb = Pt(8.5), RGBColor(0x6B, 0x72, 0x80)
                    rr.font.name = font
                for b in e.bullets:
                    self._bullet(doc, f"{t.bullet}  {b}", font, bold_prefix=False)
        elif key == "education" and c.education:
            self._heading(doc, "Education", t, font)
            for d in c.education:
                line = " — ".join(x for x in (d.degree, d.institution) if x) + \
                    (f"   ({d.start}–{d.end})".replace("()", "") if (d.start or d.end) else "")
                self._bullet(doc, line, font, bold_prefix=True)
                if d.details:
                    doc.add_paragraph(d.details)
        elif key == "skills" and c.skills:
            self._heading(doc, "Skills", t, font)
            self._bullet(doc, "  ·  ".join(c.skills), font)
        elif key == "projects" and c.projects:
            self._heading(doc, "Projects", t, font)
            for pr in c.projects:
                label = pr.name + (f"  ({pr.tech})" if pr.tech else "")
                self._bullet(doc, label + (f" — {pr.description}" if pr.description else ""), font,
                             bold_prefix=True)
                if pr.link:
                    doc.add_paragraph(f"Link: {pr.link}")
        elif key == "certifications" and c.certifications:
            self._heading(doc, "Certifications", t, font)
            for cert in c.certifications:
                meta = ", ".join(x for x in (cert.issuer, cert.year) if x)
                self._bullet(doc, f"{t.bullet}  {cert.name}" + (f" ({meta})" if meta else ""),
                             font)
        elif key == "achievements" and c.achievements:
            self._heading(doc, "Achievements", t, font)
            for a in c.achievements:
                self._bullet(doc, f"{t.bullet}  {a}", font)
        elif key == "languages" and c.languages:
            self._heading(doc, "Languages", t, font)
            self._bullet(doc, ", ".join(f"{l.name} ({l.level})" for l in c.languages), font)
        elif key == "interests" and c.interests:
            self._heading(doc, "Interests", t, font)
            self._bullet(doc, ", ".join(c.interests), font)

    def _bullet(self, doc: Document, text: str, font: str, bold_prefix: bool = False) -> None:
        """One bullet paragraph; optionally bolds the 'Head — ' prefix."""
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.space_after = Pt(1)

        use_bold_split = bold_prefix and " — " in text
        head, rest = text.split(" — ", 1) if use_bold_split else (text, "")
        if use_bold_split:
            r_bold = p.add_run(head + " — ")
            r_bold.bold = True
            r_bold.font.size, r_bold.font.name = Pt(9.5), font
            r_rest = p.add_run(rest)
        else:
            r_rest = p.add_run(text)
        r_rest.font.size = Pt(9.5)
        r_rest.font.name = font
