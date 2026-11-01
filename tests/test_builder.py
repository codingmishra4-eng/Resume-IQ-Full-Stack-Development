"""
Builder tests — ALL 15 templates must produce valid PDF, DOCX and HTML.
"""

from __future__ import annotations

import pytest

from resume_builder.builder import BuilderError, ResumeBuilder
from resume_builder.resume_data import ResumeData
from resume_builder.template_manager import build_default_templates


@pytest.fixture(scope="module")
def sample() -> ResumeData:
    return ResumeData.from_dict({
        "full_name": "Test Person", "headline": "QA Engineer",
        "email": "test@example.com", "phone": "+1 555 123 4567", "location": "Pune, India",
        "summary": "Focused QA engineer experienced with pytest, selenium and API testing.",
        "skills": ["Python", "pytest", "Selenium", "SQL"],
        "experience": [{"role": "QA Intern", "company": "Acme", "location": "Pune",
                        "start": "Jan 2025", "end": "Jun 2025",
                        "bullets": ["Automated 40 regression tests reducing cycle time"]}],
        "education": [{"degree": "B.Tech IT", "institution": "ABC College",
                       "location": "Pune", "start": "2021", "end": "2025"}],
        "projects": [{"name": "Test Framework", "tech": "pytest",
                      "description": "Built a reusable framework", "link": "github.com/x/y"}],
        "languages": [{"name": "English", "level": "Fluent"}],
        "interests": ["Reading"],
        "extra_sections": [{"title": "Volunteering", "body": "Organised college tech fest"}],
    })


class TestTemplateRegistry:
    def test_exactly_15_templates(self):
        templates = build_default_templates()
        assert len(templates) == 15
        assert len({t.id for t in templates}) == 15            # ids unique
        assert len({t.name for t in templates}) == 15          # names unique

    def test_expected_names_present(self):
        names = [t.name for t in build_default_templates()]
        for expected in ["Modern Professional", "Minimalist ATS-Friendly",
                         "Software Developer", "UI/UX Designer", "Academic Resume",
                         "Creative Professional"]:
            assert expected in names

    def test_unknown_template_rejected(self, builder):
        with pytest.raises(BuilderError):
            builder.template("does-not-exist")


class TestExports:
    def test_all_15_pdf_and_docx(self, builder, sample, tmp_path):
        for tpl in builder.list_templates():
            pdf = builder.build(sample, tpl.id, "pdf")
            docx = builder.build(sample, tpl.id, "docx")
            assert pdf.exists() and pdf.stat().st_size > 800, tpl.id
            assert docx.exists() and docx.stat().st_size > 5_000, tpl.id

    def test_all_15_html_previews(self, builder, sample):
        for tpl in builder.list_templates():
            html = builder.preview_html(sample, tpl.id)
            assert "<html" in html and "Your Name" not in html, tpl.id
            assert "Test Person" in html, tpl.id

    def test_pdf_content_is_real_text(self, builder, sample, tmp_path):
        import pymupdf
        path = builder.build(sample, "ats-minimal", "pdf")
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        assert "Test Person" in text
        assert "QA Engineer" in text or "QA ENG" in text      # ats-minimal uppercases the headline
        assert "pytest" in text

    def test_sidebar_templates_render_two_frames(self, builder, sample):
        # exactly two creative templates use the sidebar layout engine
        sidebar = [t for t in builder.list_templates() if t.layout == "sidebar"]
        assert len(sidebar) == 2
        assert all(not t.ats_friendly for t in sidebar)

    def test_template_switch_keeps_content(self, builder, sample):
        """Same data under two templates → same name extracted from PDFs."""
        import pymupdf
        texts = []
        for tpl_id in ("modern-pro", "uiux"):
            path = builder.build(sample, tpl_id, "pdf")
            doc = pymupdf.open(path)
            texts.append("\n".join(p.get_text() for p in doc))
            doc.close()
        assert "Test Person" in texts[0] and "Test Person" in texts[1]

    def test_empty_resume_rejected(self, builder, tmp_path):
        with pytest.raises(BuilderError, match="empty"):
            builder.build(ResumeData(), "modern-pro", "pdf")

    def test_bad_format_rejected(self, builder, sample):
        with pytest.raises(BuilderError, match="pdf.*docx"):
            builder.build(sample, "modern-pro", "txt")
