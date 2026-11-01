"""
Scoring engine — orchestrates one full analysis.

Pipeline:
    bytes → ResumeParser → ParsedResume
          → ATSAnalyzer   → ATSResult (six categories + overall)
          → JobMatcher    → (optional) JobMatchResult
          → report dict   → saved to the database

This is also the single place the UI calls, keeping pages simple.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import config
from backend.ai_assistant import AIAssistant
from backend.ats_analyzer import ATSAnalyzer, ATSResult
from backend.grammar_checker import GrammarChecker
from backend.job_matcher import JobMatchResult, JobMatcher
from backend.keyword_analyzer import KeywordAnalyzer
from backend.resume_parser import ParsedResume, ParseError, ResumeParser
from config import get_logger
from database.database import Database, get_db

logger = get_logger("scoring_engine")


@dataclass
class FullAnalysis:
    """Everything a "run analysis" action produces."""

    parsed: ParsedResume
    ats: ATSResult
    job_match: JobMatchResult | None = None
    suggestions: list[Any] = field(default_factory=list)
    record_id: int | None = None

    # -- convenient views --------------------------------------------------
    @property
    def overall(self) -> float:
        return self.ats.overall

    @property
    def category_scores(self) -> dict[str, float]:
        return {k: c.score for k, c in self.ats.categories.items()}

    def report_dict(self) -> dict[str, Any]:
        """Compact JSON-serialisable report used for DB + PDF export."""
        return {
            "file_name": self.parsed.file_name,
            "file_type": self.parsed.file_type,
            "word_count": self.parsed.word_count,
            "pages": self.parsed.pages,
            "contact": {
                "email": self.parsed.contact.get("email"),
                "phone": self.parsed.contact.get("phone"),
                "linkedin": self.parsed.contact.get("linkedin"),
                "counts": {"emails": len(self.parsed.emails),
                           "phones": len(self.parsed.phones),
                           "links": len(self.parsed.links)},
            },
            "section_order": self.parsed.section_order,
            "sections_found": sorted(self.parsed.sections.keys()),
            "ats": self.ats.as_dict(),
            "job_match": self.job_match.as_dict() if self.job_match else None,
            "warnings": self.parsed.warnings,
            "disclaimer": self.ats.verified_notes.get("disclaimer", ""),
        }


class ScoringEngine:
    """One entry point: `engine.analyze_upload(data, name, job_description)`."""

    def __init__(self, db: Database | None = None, ai: AIAssistant | None = None):
        self.db = db or get_db()
        self.parser = ResumeParser()
        self.analyzer = ATSAnalyzer(KeywordAnalyzer(), GrammarChecker())
        self.matcher = JobMatcher(KeywordAnalyzer())
        self.ai = ai or AIAssistant()

    # ------------------------------------------------------------------ #

    def analyze_upload(self, data: bytes, file_name: str,
                       job_description: str | None = None,
                       persist: bool = True) -> FullAnalysis:
        """Full pipeline with persistence; raises ParseError for bad files."""
        parsed = self.parser.parse(data, file_name)          # may raise ParseError
        ats = self.analyzer.analyze(parsed, job_description=job_description)
        job_match = self.matcher.match(parsed, jd_text=job_description) if job_description else None

        analysis = FullAnalysis(parsed=parsed, ats=ats, job_match=job_match)

        if persist:
            categories = analysis.category_scores
            record = self.db.save_analysis({
                "file_name": parsed.file_name,
                "file_type": parsed.file_type,
                "ats_score": ats.overall,
                "readability_score": categories.get("readability", 0.0),
                "structure_score": categories.get("structure", 0.0),
                "completeness_score": categories.get("completeness", 0.0),
                "keywords_score": categories.get("keywords", 0.0),
                "formatting_score": categories.get("formatting", 0.0),
                "contact_score": categories.get("contact", 0.0),
                "word_count": parsed.word_count,
                "job_match_score": job_match.match_score if job_match else None,
                "report_json": analysis.report_dict(),
                "resume_text": parsed.text[:150_000],
            })
            analysis.record_id = record.id
        return analysis

    def analyze_text(self, text: str, file_name: str = "pasted.txt",
                     persist: bool = False) -> FullAnalysis:
        """Analyze raw text directly (used by the builder + tests)."""
        parser = self.parser
        fake = ParsedResume(file_name=file_name, file_type="txt", text=text, pages=1)
        parser._enrich(fake)                                  # reuse enrichment
        if fake.word_count < config.MIN_WORDS_FOR_ANALYSIS:
            raise ParseError(f"Too little text to analyze ({fake.word_count} words).")
        ats = self.analyzer.analyze(fake)
        return FullAnalysis(parsed=fake, ats=ats)
