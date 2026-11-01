"""
Job matcher tests — honest matching semantics (never invents matches).
"""

from __future__ import annotations

from backend.job_matcher import JobMatcher
from backend.keyword_analyzer import KeywordAnalyzer
from backend.resume_parser import ResumeParser

JD = """Senior Data Analyst
We require 3+ years of experience with SQL, Tableau and Python for reporting.
Strong statistics knowledge; will build ETL pipelines and dashboards.
Bachelor's degree required. Communication skills essential."""

resume_parser = ResumeParser()
matcher = JobMatcher(KeywordAnalyzer())


class TestMatch:
    def test_empty_jd(self, sample_resume_bytes):
        parsed = resume_parser.parse(sample_resume_bytes, "s.docx")
        result = matcher.match(parsed, "")
        assert result.match_score == 0
        assert result.notes

    def test_skills_split_correctly(self, sample_resume_bytes):
        parsed = resume_parser.parse(sample_resume_bytes, "s.docx")
        result = matcher.match(parsed, JD)
        joined = set(result.matching) | set(result.partial) | set(result.missing)
        # every displayed skill came from one of the two texts
        assert all(s.lower() in JD.lower() for s in joined)

    def test_matching_contains_real_overlap(self, sample_resume_bytes):
        parsed = resume_parser.parse(sample_resume_bytes, "s.docx")
        result = matcher.match(parsed, JD)
        assert "python" in [s.lower() for s in result.matching] or \
               "sql" in [s.lower() for s in result.matching]

    def test_score_in_range(self, sample_resume_bytes):
        parsed = resume_parser.parse(sample_resume_bytes, "s.docx")
        result = matcher.match(parsed, JD)
        assert 0 <= result.match_score <= 100

    def test_years_requirement_detected(self, sample_resume_bytes):
        parsed = resume_parser.parse(sample_resume_bytes, "s.docx")
        result = matcher.match(parsed, JD)
        assert result.min_years == (3, 3)
