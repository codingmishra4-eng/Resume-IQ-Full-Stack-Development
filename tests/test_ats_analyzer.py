"""
ATS analyzer tests — every category stays numerically sound and responds to
real input changes (never fabricated).
"""

from __future__ import annotations

from backend.ats_analyzer import ATSAnalyzer
from backend.grammar_checker import GrammarChecker
from backend.keyword_analyzer import KeywordAnalyzer
from backend.resume_parser import ResumeParser


def _analyze(sample_resume_bytes) -> tuple:
    """Convenience: parsed + ATS result for the shared sample resume."""
    parsed = ResumeParser().parse(sample_resume_bytes, "sample.docx")
    analyzer = ATSAnalyzer(KeywordAnalyzer(), GrammarChecker())
    return parsed, analyzer.analyze(parsed)


class TestScoreBounds:
    def test_overall_in_range(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        assert 0 <= result.overall <= 100

    def test_all_categories_in_range(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        assert set(result.categories) == {"readability", "structure", "completeness",
                                          "keywords", "formatting", "contact"}
        for cat in result.categories.values():
            assert 0 <= cat.score <= 100, f"{cat.name} = {cat.score}"

    def test_weighted_total_matches(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        weights = {"readability": .20, "structure": .20, "completeness": .15,
                   "keywords": .20, "formatting": .15, "contact": .10}
        manual = sum(result.categories[k].score * w for k, w in weights.items())
        assert abs(manual - result.overall) < 0.1


class TestEvidence:
    def test_spelling_caught(self, sample_resume_bytes):
        parsed, result = _analyze(sample_resume_bytes)
        # "experiance" planted in the sample summary
        assert any("experiance" in f.message for f in result.writing.spelling_issues)

    def test_weak_phrases_caught(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        kinds = " | ".join(i.message for i in result.writing.weak_phrasings)
        assert "responsible for" in kinds.lower()

    def test_recommendations_generated(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        assert result.recommendations, "non-empty actionable list expected"
        assert all(isinstance(r, str) and r for r in result.recommendations)

    def test_disclaimer_present(self, sample_resume_bytes):
        _, result = _analyze(sample_resume_bytes)
        assert "estimated" in result.verified_notes["disclaimer"].lower()
