"""
Resume text extraction & parsing.

Goal: turn an uploaded PDF or DOCX into a structured `ParsedResume`:
  - raw text (page by page, then joined)
  - detected sections (Experience, Education, Skills, ...)
  - contact info (email, phone, LinkedIn/GitHub URLs)
  - quality flags that feed the ATS readability score

Supported reliably: .pdf (PyMuPDF), .docx (python-docx).
Not supported: legacy .doc (rejected with a clear, actionable error).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

import pymupdf

import config
from config import get_logger

logger = get_logger("resume_parser")

PARSE_ERROR = "ParseError"


class ParseError(Exception):
    """Raised with a user-facing message when a file cannot be parsed."""


# ---------------------------------------------------------------------------
# Regex patterns (compiled once — your classic falsy-regex performance story)
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3,5}\)?[\s.-]?)\d{3}[\s.-]?\d{2,4}"
)
URL_RE = re.compile(r"(https?://\S+|www\.[\w\-./?=&#]+|linkedin\.com/\S+|github\.com/\S+)")
NON_WORD_RE = re.compile(r"\W+")

# Canonical section names — key is our internal name, values are variants found
# in the wild (case-insensitive match on the whole heading line).
SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["summary", "professional summary", "profile", "objective",
                "career objective", "about me", "personal statement"],
    "experience": ["work experience", "experience", "professional experience",
                   "employment history", "career history", "work history",
                   "internship", "internships", "professional background"],
    "education": ["education", "academic background", "academics", "qualifications", "educational qualifications"],
    "skills": ["skills", "technical skills", "core skills", "key skills",
               "skill set", "competencies", "technologies", "tech stack"],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "portfolio"],
    "certifications": ["certifications", "certificates", "licenses", "courses", "trainings"],
    "achievements": ["achievements", "awards", "accomplishments", "honors", "honours", "recognition"],
    "languages": ["languages", "language proficiency"],
    "extras": ["interests", "hobbies", "volunteer", "volunteering", "activities", "publications", "references"],
}

# A heading-like line recognizer used by a future lint pass (kept simple).
SECTION_LINE_RE = re.compile(r"^\s*([A-Z][A-Za-z&/ ]{2,40})\s*:?\s*$")


def _canonical_section(heading: str) -> str | None:
    """Map a raw heading line like 'WORK HISTORY' to 'experience'."""
    cleaned = heading.strip().rstrip(":").lower()
    cleaned = re.sub(r"[^a-z ]", "", cleaned).strip()
    for canonical, aliases in SECTION_ALIASES.items():
        if any(cleaned == a or (len(a) > 3 and a in cleaned) for a in aliases):
            return canonical
    return None


@dataclass
class ParsedResume:
    """Everything we reliably know about an uploaded resume."""

    file_name: str
    file_type: str                 # 'pdf' | 'docx'
    text: str = ""                 # full extracted text
    pages: int = 0
    word_count: int = 0
    sections: dict[str, str] = field(default_factory=dict)   # canonical -> body
    section_order: list[str] = field(default_factory=list)
    contact: dict[str, str | None] = field(default_factory=dict)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    bullet_count: int = 0
    tables_detected: int = 0
    images_detected: int = 0
    image_chars: int = 0           # characters lost to image pages (PDF)
    headings_look_caps: bool = False
    warnings: list[str] = field(default_factory=list)        # user-facing flags
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def has_min_text(self) -> bool:
        """Enough text for a meaningful analysis?"""
        return self.word_count >= config.MIN_WORDS_FOR_ANALYSIS


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_pdf(data: bytes) -> ParsedResume:
    """Parse a PDF via PyMuPDF: text per page + image/table diagnostics."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except RuntimeError as exc:
        raise ParseError("This PDF appears to be corrupted or password-protected.") from exc

    page_texts: list[str] = []
    image_chars = 0
    images_total = 0
    result = ParsedResume(file_name="resume.pdf", file_type="pdf")

    for page in doc:
        page_texts.append(page.get_text("text") or "")
        images_total += len(page.get_images(full=True))
        # If a page contributes almost no text but has images, it is likely a
        # scan / graphic-heavy page — ATs read little from it. Track the ratio.
        if len(page.get_text("words")) <= 5 and page.get_images(full=True):
            image_chars += len(page_texts[-1])

    result.pages = doc.page_count
    doc.close()

    result.text = "\n\n".join(t.strip() for t in page_texts)
    result.images_detected = images_total
    result.image_chars = image_chars
    return result


def _extract_docx(data: bytes) -> ParsedResume:
    """Parse a DOCX via python-docx: paragraphs + table cell text."""
    from docx import Document as DocxDocument
    from docx.document import Document as _Doc
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc: _Doc = DocxDocument(io.BytesIO(data))
    except Exception as exc:                                   # noqa: BLE001
        raise ParseError("This DOCX file could not be opened. Is it a valid Word document?") from exc

    chunks: list[str] = []
    tables = 0
    tables_with_text = 0

    for block in doc.element.body.iterchildren():
        if block.tag.endswith("}p"):
            para = Paragraph(block, doc)
            style = ""
            try:
                style = (para.style.name or "").lower()
            except Exception:                                   # noqa: BLE001
                pass
            text = para.text.strip()
            if not text:
                continue
            # Preserve list bullets so bullet analysis works for DOCX too.
            prefix = "• " if "list" in style else ""
            chunks.append(prefix + text)
        elif block.tag.endswith("}tbl"):
            tables += 1
            table = Table(block, doc)
            cell_text = [cell.text.strip() for row in table.rows for cell in row.cells]
            if any(cell_text):
                tables_with_text += 1
                chunks.extend(t for t in cell_text if t)

    result = ParsedResume(file_name="resume.docx", file_type="docx")
    result.text = "\n".join(chunks)
    result.pages = 1
    result.tables_detected = tables_with_text
    return result


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _detect_sections(text: str) -> tuple[dict[str, str], list[str]]:
    """Split raw text into canonical sections using heading heuristics."""
    sections: dict[str, str] = {}
    current: str | None = None
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        candidate = None
        if 0 < len(stripped) <= 48:
            # A heading is short, title-like, and (usually) not a sentence.
            words = stripped.split()
            sentence_like = bool(re.search(r"[,;.]", stripped.rstrip("."))) or len(words) > 8
            # Title-ish if ALL CAPS or first word starts uppercase, not a sentence.
            titleish = (stripped.isupper() or (words and words[0][:1].isupper())) and not sentence_like
            if titleish:
                candidate = _canonical_section(stripped)
        if candidate:
            current = candidate
            sections.setdefault(current, "")
        elif current is not None:
            sections[current] += line + "\n"

    order: list[str] = []
    for line in lines:                       # recompute order robustly
        s = line.strip()
        if 0 < len(s) <= 48:
            c = _canonical_section(s)
            if c and c in sections and c not in order:
                order.append(c)
    return sections, order


def _extract_contact(text: str) -> dict[str, Any]:
    emails = EMAIL_RE.findall(text)
    # The phone regex returns grouped tuples; grab the full matched strip instead.
    spans = [m.group(0).strip() for m in PHONE_RE.finditer(text)]
    urls = URL_RE.findall(text)
    linkedin = next((u for u in urls if "linkedin.com" in u.lower()), None)
    github = next((u for u in urls if "github.com" in u.lower()), None)
    return {
        "emails": list(dict.fromkeys(e.lower() for e in emails))[:5],
        "phones": list(dict.fromkeys(spans))[:5],
        "links": list(dict.fromkeys(u.rstrip(".,);") for u in urls))[:8],
        "linkedin": linkedin,
        "github": github,
        "email": emails[0] if emails else None,
        "phone": spans[0] if spans else None,
    }


class ResumeParser:
    """Facade that validates an upload and returns a ParsedResume."""

    MAX_BYTES = config.MAX_UPLOAD_BYTES

    def parse(self, data: bytes, file_name: str) -> ParsedResume:
        """Validate → extract → enrich. Raises ParseError with user message."""
        suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        if file_name.lower().endswith(".doc"):
            raise ParseError(
                "Legacy .doc format is not supported reliably by parsers. "
                "Please save your resume as .docx (Word → Save As → .docx) or export a PDF, then re-upload."
            )

        if suffix not in config.ALLOWED_EXTENSIONS:
            raise ParseError("Unsupported file type. Please upload a PDF or DOCX resume.")

        if len(data) == 0:
            raise ParseError("The uploaded file is empty.")
        if len(data) > self.MAX_BYTES:
            limit = config.MAX_UPLOAD_MB
            raise ParseError(f"File is larger than the {limit:g} MB limit. Please upload a smaller file.")

        if suffix == ".pdf":
            parsed = _extract_pdf(data)
        else:
            parsed = _extract_docx(data)

        parsed.file_name = file_name
        self._enrich(parsed)
        return parsed

    # ------------------------------------------------------------------ #

    def _enrich(self, parsed: ParsedResume) -> None:
        """Fold contact info, sections and quality warnings into the result."""
        text = parsed.text
        cleaned = text.replace("\u00a0", " ")
        parsed.word_count = len([w for w in NON_WORD_RE.split(cleaned) if w])

        parsed.sections, parsed.section_order = _detect_sections(cleaned)
        parsed.contact = _extract_contact(cleaned)

        parsed.emails = parsed.contact.get("emails", [])          # type: ignore[assignment]
        parsed.phones = parsed.contact.get("phones", [])          # type: ignore[assignment]
        parsed.links = parsed.contact.get("links", [])            # type: ignore[assignment]

        first_line = next((l for l in cleaned.splitlines() if l.strip()), "")
        name_guess = first_line.strip()[:60] if first_line and len(first_line.split()) <= 6 else None
        parsed.meta["name_guess"] = name_guess

        parsed.bullet_count = sum(
            1 for line in cleaned.splitlines()
            if re.match(r"^\s*([•●▪·*]|[-–]\s|\u2013)\s*\S", line)
        )

        # --- quality flags (user-facing) ---------------------------------
        if not parsed.emails:
            parsed.warnings.append("No email address was found — recruiters need one way to reach you.")
        elif not parsed.phones:
            parsed.warnings.append("No phone number detected in the header area.")

        if parsed.file_type == "pdf":
            if parsed.pages == 0:
                raise ParseError("The PDF contains no readable pages.")
            if parsed.word_count < config.MIN_WORDS_FOR_ANALYSIS:
                if parsed.images_detected > 0:
                    raise ParseError(
                        "Almost no selectable text was found and the PDF contains images — it is likely a "
                        "scanned/image-only resume. ATS software cannot read it. Please upload a text-based PDF."
                    )
                raise ParseError(
                    f"Only {parsed.word_count} readable words found — the document looks empty or corrupted."
                )
            if parsed.image_chars > 0:
                parsed.warnings.append(
                    "Some pages appear to be image-heavy with little readable text — ATs may miss that content."
                )
            if parsed.images_detected > 3:
                parsed.warnings.append(
                    "Multiple embedded images were detected. Many ATS platforms skip or mishandle graphics."
                )
        else:
            if parsed.word_count < config.MIN_WORDS_FOR_ANALYSIS:
                raise ParseError(
                    f"Only {parsed.word_count} readable words found — the document looks empty or corrupted."
                )
            if parsed.tables_detected:
                parsed.warnings.append(
                    "Text inside tables was found. Some ATS software reads tables out of order — prefer plain layout."
                )

        header = "\n".join(cleaned.splitlines()[:12])
        parsed.headings_look_caps = bool(re.search(r"^[A-Z][A-Z\s&/]{2,}$", header, re.MULTILINE))

        zero_len_pages_evidence = cleaned.count("\n\n\n")  # rough gaps after joins
        parsed.meta["blank_line_gaps"] = zero_len_pages_evidence
