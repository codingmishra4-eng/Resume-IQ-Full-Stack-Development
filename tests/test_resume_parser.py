"""
Resume parser tests — validation, extraction, and error handling.
"""

from __future__ import annotations

import pytest

from backend.resume_parser import ParseError, ResumeParser

parser = ResumeParser()


class TestValidation:
    def test_rejects_legacy_doc(self):
        with pytest.raises(ParseError, match="docx"):
            parser.parse(b"anything", "old_resume.doc")

    def test_rejects_unknown_extension(self):
        with pytest.raises(ParseError):
            parser.parse(b"whatever", "resume.rtf")

    def test_rejects_empty_file(self):
        with pytest.raises(ParseError, match="empty"):
            parser.parse(b"", "resume.pdf")

    def test_rejects_oversized(self, monkeypatch):
        monkeypatch.setattr(parser, "MAX_BYTES", 10)
        with pytest.raises(ParseError, match="limit"):
            parser.parse(b"x" * 50, "resume.pdf")

    def test_rejects_fake_pdf(self):
        with pytest.raises(ParseError):
            parser.parse(b"this is not a pdf", "resume.pdf")


class TestDocxParsing:
    def test_extracts_text(self, sample_resume_bytes):
        parsed = parser.parse(sample_resume_bytes, "priya.docx")
        assert parsed.word_count > 100
        assert parsed.file_type == "docx"

    def test_contact_extraction(self, sample_resume_bytes):
        parsed = parser.parse(sample_resume_bytes, "priya.docx")
        assert parsed.contact.get("email") == "priya.sharma@example.com"
        assert parsed.contact.get("phone")
        assert parsed.contact.get("linkedin")

    def test_section_detection(self, sample_resume_bytes):
        parsed = parser.parse(sample_resume_bytes, "priya.docx")
        assert "experience" in parsed.section_order
        assert "education" in parsed.section_order
        assert "skills" in parsed.section_order

    def test_empty_docx_detected(self, builder):
        # the builder refuses empty resumes; craft an empty DOCX manually
        from docx import Document
        import io
        buf = io.BytesIO()
        Document().save(buf)
        with pytest.raises(ParseError, match="words"):
            parser.parse(buf.getvalue(), "empty.docx")
