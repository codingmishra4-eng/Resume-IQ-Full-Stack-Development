"""
ATS compatibility analyzer.

Six evidence-based categories (each scored 0–100 from real resume data):

  readability    — can text be extracted cleanly? (extraction quality, images,
                   tables, word count sanity)
  structure      — are standard sections present and in sensible order?
  completeness   — which content sections exist & have content?
  keywords       — vocabulary coverage, action verbs, keyword density
  formatting     — bullets, dates, symbols, flags that commonly confuse ATS
  contact        — parseable email / phone / location-ish info

The combined score uses config.ScoreWeights. The result is explicitly labelled
"estimated ATS compatibility" — never an official vendor score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import config
from backend.grammar_checker import GrammarChecker, WritingReport
from backend.keyword_analyzer import KeywordAnalyzer, KeywordReport
from backend.resume_parser import ParsedResume
from config import get_logger

logger = get_logger("ats_analyzer")

DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*'?(\d{2,4})\b"
    r"|(\d{1,2}/\d{4})|(\d{4}\s*[-–]\s*(present|\d{4}))", re.IGNORECASE)

# Section groups expected for a complete resume.
REQUIRED_SECTIONS = ["contact_header", "summary", "experience", "education", "skills"]
RECOMMENDED_SECTIONS = ["projects", "certifications", "achievements", "languages"]


@dataclass
class CategoryResult:
    """One scored category with the evidence behind it (for UI display)."""

    name: str
    score: float
    weight: float
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add_check(self, ok: bool | str, label: str, detail: str = "") -> None:
        """Record one atomic check. ok: True/False/'warn'."""
        self.checks.append({"status": "pass" if ok is True else ("warn" if ok == "warn" else "fail"),
                            "label": label, "detail": detail})

    def as_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "weight": self.weight, "checks": self.checks}


@dataclass
class ATSResult:
    """Full analysis result for one resume."""

    overall: float = 0.0
    categories: dict[str, CategoryResult] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    writing: WritingReport | None = None
    keywords: KeywordReport | None = None
    verified_notes: dict[str, Any] = field(default_factory=dict)

    def categories_sorted(self) -> list[CategoryResult]:
        weights = config.DEFAULT_WEIGHTS
        order = [w for w in weights.normalized()]
        return [self.categories[c] for c in order if c in self.categories]

    def as_dict(self) -> dict:
        return {
            "overall": self.overall,
            "categories": {k: v.as_dict() for k, v in self.categories.items()},
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
            "writing": None if self.writing is None else {
                "spelling": [i.as_dict() for i in self.writing.spelling_issues],
                "grammar": [i.as_dict() for i in self.writing.grammar_issues],
                "weak_phrasings": [i.as_dict() for i in self.writing.weak_phrasings],
                "long_sentences": self.writing.long_sentences,
                "passive_count": self.writing.passive_count,
                "buzzwords": self.writing.buzzwords_found,
                "repeated_words": self.writing.repeated_words,
            },
            "verified_notes": self.verified_notes,
        }


class ATSAnalyzer:
    """Compute the estimated ATS compatibility score from a ParsedResume."""

    def __init__(self, keyword_analyzer: KeywordAnalyzer | None = None,
                 grammar_checker: GrammarChecker | None = None):
        self.keyword_analyzer = keyword_analyzer or KeywordAnalyzer()
        self.grammar = grammar_checker or GrammarChecker()
        self.weights = config.DEFAULT_WEIGHTS.normalized()

    # ------------------------------------------------------------------ #

    def analyze(self, resume: ParsedResume, job_description: str | None = None) -> ATSResult:
        logger.info("Analyzing %s (%s words, %s pages)", resume.file_name,
                    resume.word_count, resume.pages)

        result = ATSResult()
        result.categories = {
            "readability": self._score_readability(resume),
            "structure": self._score_structure(resume),
            "completeness": self._score_completeness(resume),
            "keywords": self._score_keywords(resume),
            "formatting": self._score_formatting(resume),
            "contact": self._score_contact(resume),
        }

        # Weighted overall score, 0–100, rounded to one decimal.
        for cat in result.categories.values():
            cat.score = max(0.0, min(100.0, float(cat.score)))   # guard against threshold drift
        result.overall = round(sum(
            result.categories[name].score * weight
            for name, weight in self.weights.items()
        ), 1)

        result.writing = self.grammar.check(resume.text)
        result.keywords = self.keyword_analyzer.analyze(resume.text)
        self._derive_strengths_weaknesses(result)
        self._build_recommendations(result, resume, job_description)
        result.verified_notes["disclaimer"] = (
            "Estimated ATS compatibility score computed by ResumeIQ heuristics. "
            "It is not certified by any ATS vendor; individual systems parse and rank differently."
        )
        return result

    # -------------------------- categories ----------------------------- #

    def _score_readability(self, r: ParsedResume) -> CategoryResult:
        cat = CategoryResult("readability", 0.0, self.weights["readability"])
        # 1. Word-count sanity: extremely short resumes look broken to parsers.
        if r.word_count >= 300:
            cat.score += 40
            cat.add_check(True, "Text volume", f"{r.word_count} words extracted")
        elif r.word_count >= 150:
            cat.score += 30
            cat.add_check("warn", "Text volume", f"{r.word_count} words — rather short")
        elif r.word_count >= config.MIN_WORDS_FOR_ANALYSIS:
            cat.score += 18
            cat.add_check(False, "Text volume", f"Only {r.word_count} words — very thin content")
        else:
            cat.add_check(False, "Text volume", f"Only {r.word_count} words")

        # 2. Image-only / scanned content (PDFs)
        if r.file_type == "pdf":
            if r.image_chars == 0:
                cat.score += 25
                cat.add_check(True, "No image-only pages detected")
            else:
                cat.add_check(False, "Image-only pages detected",
                              "Content on image pages is invisible to ATS parsers")

        # 3. Tables (DOCX)
        if r.file_type == "docx" and r.tables_detected:
            cat.score += 15
            cat.add_check("warn", "Text found inside tables",
                          "Some ATS read table content out of order")
        else:
            cat.score += 25
            cat.add_check(True, "No suspicious table layouts")

        # 4. Extraction quality — blank-line gaps / broken tokens
        blank_gaps = r.meta.get("blank_line_gaps", 0)
        if blank_gaps <= 3:
            cat.score += 20
            cat.add_check(True, "Clean text extraction")
        else:
            cat.score += 10
            cat.add_check("warn", "Uneven text extraction", "Multiple large blank runs detected")

        # 5. Encoding sanity — mojibake (Ã, â€™) hints broken encoding
        if not re.search(r"(Ã|â€|Â)\w", r.text):
            cat.score += 15
            cat.add_check(True, "Character encoding looks normal")
        else:
            cat.add_check(False, "Possible character-encoding corruption (Ã / â€ sequences)")
        return cat

    def _score_structure(self, r: ParsedResume) -> CategoryResult:
        cat = CategoryResult("structure", 0.0, self.weights["structure"])
        found = r.section_order
        core = [s for s in ("summary", "experience", "education", "skills") if s in found]

        # Proportional credit for core sections found.
        cat.score += 55 * (len(core) / 4)
        if len(core) == 4:
            cat.add_check(True, "All four core sections detected", ", ".join(core))
        else:
            missing = [s for s in ("summary", "experience", "education", "skills") if s not in found]
            cat.add_check(False, "Missing standard sections", ", ".join(missing) if missing else "none")

        if len(r.section_order) >= 5:
            cat.score += 20
            cat.add_check(True, "Rich section set",
                          f"{len(r.section_order)} sections: {', '.join(r.section_order)}")
        elif len(r.section_order) >= 3:
            cat.score += 10
            cat.add_check("warn", "Limited sections", f"Only {len(r.section_order)} detected")

        # Headings style: ALL-CAPS long headers can over- or under-take parsers.
        if r.headings_look_caps:
            cat.score += 15
            cat.add_check(True, "Clear uppercase section headings")
        else:
            cat.score += 10
            cat.add_check("warn", "Section headings not visually distinct",
                          "Consider bold or ALL-CAPS headings for clarity")

        # Contact block in the top 8 lines
        head = "\n".join(r.text.splitlines()[:8])
        if r.contact.get("email") and r.contact["email"] in head:
            cat.score += 10
            cat.add_check(True, "Contact info in the top block (parser-friendly)")
        else:
            cat.add_check("warn", "Contact info not found near the top of the resume")
        return cat

    def _score_completeness(self, r: ParsedResume) -> CategoryResult:
        # Budget: required 36 + optional 30 + summary 12 + bullets 12 + dates 10 = 100.
        cat = CategoryResult("completeness", 0.0, self.weights["completeness"])
        sections = r.sections

        required_present = [s for s in ("experience", "education", "skills") if s in sections]
        cat.score += 12 * len(required_present)
        missing_required = [s for s in ("experience", "education", "skills") if s not in sections]
        if missing_required:
            cat.add_check(False, "Required sections missing", ", ".join(missing_required))
        else:
            cat.add_check(True, "All required sections present")

        optional_present = [s for s in ("projects", "certifications", "achievements", "languages")
                            if s in sections]
        cat.score += 10 * min(len(optional_present), 3)
        if optional_present:
            cat.add_check(True, "Supporting sections included", ", ".join(optional_present))
        else:
            cat.add_check("warn", "No supporting sections",
                          "Projects / certifications / achievements add credibility")

        has_summary = bool(sections.get("summary", "").strip())
        if has_summary:
            summary_txt = sections["summary"].strip()
            n_words = len(summary_txt.split())
            if 25 <= n_words <= 120:
                cat.score += 12
                cat.add_check(True, "Professional summary present", f"{n_words} words")
            else:
                cat.score += 8
                cat.add_check("warn", "Summary length outside the 25–120 word sweet spot",
                              f"currently {n_words} words")
        else:
            cat.add_check(False, "No professional summary/profile detected")

        # Experience detail: bullets evidence & date evidence
        exp_text = sections.get("experience", "") or r.text
        bullets = sum(1 for line in exp_text.splitlines()
                      if re.match(r"^\s*([•●▪·*]|[-–]\s)\s*\S", line))
        if bullets >= 5:
            cat.score += 12
            cat.add_check(True, "Detailed experience bullets", f"{bullets} bullet points")
        elif bullets >= 2:
            cat.score += 7
            cat.add_check("warn", "Few experience bullets", f"only {bullets} found")
        else:
            cat.add_check(False, "Experience not written as bullet points")

        if DATE_RE.search(exp_text):
            cat.score += 10
            cat.add_check(True, "Dated experience entries found")
        else:
            cat.add_check(False, "No dates found in the Experience section",
                          "Add month/year ranges so ATS can compute tenure")
        return cat

    def _score_keywords(self, r: ParsedResume) -> CategoryResult:
        cat = CategoryResult("keywords", 0.0, self.weights["keywords"])
        rep = self.keyword_analyzer.analyze(r.text)

        # Matched taxonomy coverage (against a generic professional baseline).
        ratio = rep.total_matched / 60
        cat.score += round(40 * min(ratio, 1.0), 1)
        if rep.total_matched >= 15:
            cat.add_check(True, "Strong industry vocabulary",
                          f"{rep.total_matched} recognisable skill/keyword terms")
        elif rep.total_matched >= 6:
            cat.add_check("warn", "Moderate keyword coverage", f"{rep.total_matched} terms found")
        else:
            cat.add_check(False, "Low keyword coverage", f"only {rep.total_matched} terms found")

        verbs = len(rep.action_verbs_found)
        if verbs >= 12:
            cat.score += 30
            cat.add_check(True, "Action-verb usage", f"{verbs} distinct action verbs")
        elif verbs >= 5:
            cat.score += 20
            cat.add_check("warn", "Could use more action verbs", f"{verbs} distinct verbs found")
        else:
            cat.add_check(False, "Very few action verbs", f"only {verbs} distinct verbs found")

        if rep.overused_terms:
            cat.score += 10
            cat.add_check("warn", "Some terms repeated heavily",
                          ", ".join(w for w, _ in rep.overused_terms[:4]))
        else:
            cat.score += 15
            cat.add_check(True, "No severe keyword stuffing")

        # Quantified impact evidence: numbers, %, currency in bullets
        quant = self._quantified_bullets(r)
        if quant["count"] >= 4:
            cat.score += 15
            cat.add_check(True, "Quantified achievements", f"{quant['count']} bullets contain numbers")
        else:
            cat.add_check("warn", "Few quantified achievements",
                          f"{quant['count']} of {max(quant['bullets'], 1)} bullets contain metrics")
        return cat

    def _score_formatting(self, r: ParsedResume) -> CategoryResult:
        cat = CategoryResult("formatting", 0.0, self.weights["formatting"])

        # Bullet style consistency
        bullet_lines = re.findall(r"^\s*([•●▪·*]|[-–])\s*", r.text, re.MULTILINE)
        if not bullet_lines:
            cat.add_check("warn", "No bullet points found — resumes lacking bullets read poorly",
                          "")
            cat.score += 15
        else:
            style_counts: dict[str, int] = {}
            for b in bullet_lines:
                style_counts[b] = style_counts.get(b, 0) + 1
            consistent = max(style_counts.values()) / len(bullet_lines) >= 0.85
            if consistent:
                main_style = max(style_counts, key=style_counts.get)
                cat.score += 35
                cat.add_check(True, "Consistent bullet style",
                              f"“{main_style}” used in {style_counts[main_style]} of {len(bullet_lines)} bullets")
            else:
                cat.score += 18
                cat.add_check("warn", "Mixed bullet characters")
                cat.add_check(False, "Inconsistent bullet glyphs",
                              ", ".join(f"{k!r}×{v}" for k, v in sorted(style_counts.items())))

        # Date consistency (presence is scored; mixed formats flagged below)
        dates = DATE_RE.findall(r.text)
        if dates:
            cat.score += 20
            cat.add_check(True, "Dates present", f"{len(dates)} date references")
        else:
            cat.add_check(False, "No recognizable dates anywhere")

        # Unusual symbols that historically break ATS parsing
        weird = re.findall(r"[★☆✓✗♦◆▲►●◆️✱‣⇢]", r.text)
        if weird:
            cat.score += 20
            cat.add_check("warn", "Unusual symbols detected",
                          "Some ATS mis-read glyphs like ★ ✓ ▲ — prefer plain bullets (- or •)")
        else:
            cat.score += 15
            cat.add_check(True, "No exotic symbols")

        # Excessive ellipses / exclamation marks (tone)
        exclam = r.text.count("!")
        if exclam >= 2:
            cat.add_check("warn", "Exclamation marks in a resume are unprofessional", f"found {exclam}")
            cat.score += 8
        else:
            cat.score += 10

        # Length discipline
        pages_pen = 0
        if r.file_type == "pdf":
            if r.pages <= 2:
                cat.score += 20
                cat.add_check(True, "Resume length", f"{r.pages} page(s) — ATS-friendly length")
            else:
                pages_pen = max(0, 20 - (r.pages - 2) * 5)
                cat.score += pages_pen
                cat.add_check("warn", "Resume length over 2 pages",
                              f"{r.pages} pages; later pages are often skipped")
        else:
            cat.score += 15
            cat.add_check("warn", "DOCX page length not measured precisely",
                          "Keep it to 1–2 pages")
        return cat

    def _score_contact(self, r: ParsedResume) -> CategoryResult:
        cat = CategoryResult("contact", 0.0, self.weights["contact"])
        c = r.contact
        if c.get("email"):
            cat.score += 35
            cat.add_check(True, "Email present")
        else:
            cat.add_check(False, "No email found")

        if c.get("phone"):
            cat.score += 30
            cat.add_check(True, "Phone present")
        else:
            cat.add_check(False, "No phone number found")

        if c.get("linkedin") or any("linkedin" in (l or "").lower() for l in c.get("links", [])):
            cat.score += 20
            cat.add_check(True, "LinkedIn profile link found")
        else:
            cat.add_check("warn", "No LinkedIn link detected")

        has_location = bool(re.search(
            r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*(?:[A-Z]{2}|[A-Z][a-z]+))\b|"
            r"\b(india|bengaluru|bangalore|delhi|mumbai|hyderabad|chennai|pune|kolkata)\b",
            r.text, re.IGNORECASE))
        if has_location:
            cat.score += 15
            cat.add_check(True, "Location/city information found")
        else:
            cat.add_check("warn", "No city/location detected — include at least city and country")
        return cat

    # ---------------------- helpers & summaries -------------------------- #

    def _quantified_bullets(self, r: ParsedResume) -> dict[str, int]:
        bullets = [l for l in r.text.splitlines() if re.match(r"^\s*([•●▪·*]|[-–]\s)\s*\S", l)]
        quantified = [b for b in bullets
                      if re.search(r"\d|%", b) and not re.search(r"^\s*[•●▪·*]\s*\d*20\d\d", b)]
        return {"count": len(quantified), "bullets": len(bullets)}

    def _derive_strengths_weaknesses(self, result: ATSResult) -> None:
        for name, cat in result.categories.items():
            if cat.score >= 75:
                result.strengths.append(f"{cat.name.title()}: strong ({cat.score:.0f}/100)")
            elif cat.score <= 45:
                result.weaknesses.append(f"{cat.name.title()}: weak ({cat.score:.0f}/100)")

    def _build_recommendations(self, result: ATSResult, resume: ParsedResume,
                               jd_text: str | None) -> None:
        recs = result.recommendations

        if result.categories["contact"].score < 75:
            missing = []
            if not resume.contact.get("email"):
                missing.append("a professional email address")
            if not resume.contact.get("phone"):
                missing.append("a phone number")
            if missing:
                recs.append("Add " + " and ".join(missing) + " at the very top of the resume.")

        if resume.sections and "summary" not in resume.sections:
            recs.append("Write a 3–4 line professional summary containing your role, "
                        "experience level and one quantified win.")

        writing = result.writing
        if writing:
            if writing.spelling_issues:
                recs.append(f"Fix likely misspellings ({len(writing.spelling_issues)} found) — "
                            "spelling errors are the fastest way to get rejected.")
            if writing.weak_phrasings:
                recs.append("Replace weak phrases like “responsible for” or “worked on” "
                            "with strong action verbs (built, led, automated…).")
            if writing.long_sentences:
                recs.append(f"Split long sentences ({len(writing.long_sentences)} exceed 34 words); "
                            "bullets under 25 words scan better in ATS and for recruiters.")

        fmt = result.categories["formatting"]
        for check in fmt.checks:
            if check["status"] in ("fail", "warn"):
                label = check["label"].lower()
                recs.append(f"Formatting: {label} — {check['detail']}.".rstrip(" —."))

        if result.keywords and result.keywords.total_matched < 10:
            recs.append("Sprinkle concrete skills/keywords (tools, methods, technologies) "
                        "NATURALLY through your experience bullets — match the wording "
                        "used in your target job descriptions.")

        quant = self._quantified_bullets(resume)
        if quant["count"] < 3:
            recs.append("Add measurable results with real numbers you can verify: ≥3 bullets "
                        "with %, time saved, revenue, users or scale. Never invent metrics.")

        if jd_text:
            recs.append("Run the Job Match tab to see exactly which job keywords are missing.")
        # De-duplicate while preserving order
        seen: set[str] = set()
        result.recommendations = [r for r in recs if not (r in seen or seen.add(r))]
