"""
Builder orchestrator — one call → styled file on disk.

    builder.build(resume_data, template_id, fmt) -> path
    builder.build_preview_html(resume_data, template_id) -> str

Calls JSON save/load of built resumes via the database is handled at the UI
layer; this module stays pure (data + template in, byte stream/path out).
"""

from __future__ import annotations

import re
from pathlib import Path

import config
from config import get_logger
from resume_builder.docx_generator import ResumeDOCXGenerator
from resume_builder.pdf_generator import ResumePDFGenerator
from resume_builder.resume_data import ResumeData
from resume_builder.template_manager import ResumeTemplate, TemplateManager, get_template_manager

logger = get_logger("builder")


class BuilderError(Exception):
    """Raised with a user-facing message when generation fails."""


def _safe_filename(name: str) -> str:
    """Turn a resume name into a filesystem-stem."""
    stem = re.sub(r"[^\w\s-]", "", (name or "resume")).strip()
    stem = re.sub(r"[\s_]+", "_", stem) or "resume"
    return stem[:80]


class ResumeBuilder:
    """Facade used by pages; owns the template registry + two generators."""

    def __init__(self, templates: TemplateManager | None = None,
                 out_dir: Path | None = None):
        self.templates = templates or get_template_manager()
        self.pdf = ResumePDFGenerator()
        self.docx = ResumeDOCXGenerator()
        self.out_dir = out_dir or config.GENERATED_DIR

    def template(self, template_id: str) -> ResumeTemplate:
        tpl = self.templates.get(template_id)
        if not tpl:
            raise BuilderError(f"Unknown template '{template_id}'.")
        return tpl

    # ------------------------------------------------------------------ #
    def build(self, resume: ResumeData, template_id: str, fmt: str) -> Path:
        """Generate a PDF or DOCX file for the given resume + template."""
        tpl = self.template(template_id)
        if not resume.has_content():
            raise BuilderError("Cannot generate an empty resume — fill in some sections first.")
        fmt = fmt.lower()
        stem = _safe_filename(resume.full_name or "resume")
        suffix = {"pdf": ".pdf", "docx": ".docx"}.get(fmt)
        if not suffix:
            raise BuilderError("Format must be 'pdf' or 'docx'.")

        out = self.out_dir / f"{stem}__{tpl.id}{suffix}"
        logger.info("Building %s for '%s' with template %s", fmt.upper(), stem, tpl.id)
        try:
            if fmt == "pdf":
                return self.pdf.generate(resume, tpl, out)
            return self.docx.generate(resume, tpl, out)
        except BuilderError:
            raise
        except Exception as exc:                                   # whole-file safety net
            logger.exception("Generation failed")
            raise BuilderError(f"{fmt.upper()} generation failed: {type(exc).__name__}") from exc

    def preview_html(self, resume: ResumeData, template_id: str) -> str:
        """Self-contained HTML for the Streamlit live preview pane."""
        tpl = self.template(template_id)
        return self.templates.render_html(resume, tpl)

    def list_templates(self) -> list[ResumeTemplate]:
        return self.templates.all()
