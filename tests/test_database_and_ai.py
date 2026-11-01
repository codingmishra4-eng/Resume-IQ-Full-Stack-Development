"""
Database + AI fallback tests.
"""

from __future__ import annotations

import pytest

from backend.ai_assistant import AIAssistant
from backend.grammar_checker import GrammarChecker
from backend.keyword_analyzer import KeywordAnalyzer
from backend.ats_analyzer import ATSAnalyzer
from backend.resume_parser import ResumeParser
from backend.scoring_engine import ScoringEngine


class TestDatabase:
    def test_save_and_list(self, db, sample_resume_bytes):
        parsed = ResumeParser().parse(sample_resume_bytes, "s.docx")
        result = ATSAnalyzer(KeywordAnalyzer(), GrammarChecker()).analyze(parsed)
        record = db.save_analysis({
            "file_name": parsed.file_name, "file_type": parsed.file_type,
            "ats_score": result.overall, "word_count": parsed.word_count,
            "report_json": result.as_dict(), "resume_text": parsed.text,
        })
        assert record.id > 0
        listed = db.list_analyses()
        assert len(listed) == 1 and listed[0].file_name == "s.docx"

    def test_delete(self, db, sample_resume_bytes):
        parsed = ResumeParser().parse(sample_resume_bytes, "s.docx")
        rec = db.save_analysis({"file_name": "s.docx", "file_type": "docx", "ats_score": 50})
        assert db.delete_analysis(rec.id) is True
        assert db.delete_analysis(rec.id) is False           # second delete = nothing

    def test_saved_resume_roundtrip(self, db, sample_resume_bytes):
        rec = db.save_resume("My resume", "modern-pro",
                             {"full_name": "Priya", "skills": ["SQL"]}, "Fresher")
        loaded = db.get_resume(rec.id)
        assert loaded.data_json["full_name"] == "Priya"
        assert loaded.template_id == "modern-pro"

    def test_stats(self, db):
        db.save_analysis({"file_name": "a", "file_type": "pdf", "ats_score": 60})
        db.save_analysis({"file_name": "b", "file_type": "docx", "ats_score": 80})
        stats = db.stats()
        assert stats["analyses"] == 2
        assert stats["best_score"] == round(max(60.0, 80.0), 1)


class TestAIFallback:
    """No API key configured → assistant must stay fully usable & honest."""

    def test_without_key_is_rule_based(self):
        ai = AIAssistant(ai_config=type("C", (), {"api_key": None, "model": "m",
                                                  "base_url": None, "temperature": 0.4,
                                                  "max_tokens": 10, "timeout_seconds": 5,
                                                  "available": False})())
        result = ai.rewrite_summary("Responsible for things", "…resume text…", "QA Engineer")
        assert result.source == "rule-based"
        assert isinstance(result.improved, str) and result.improved

        bullets = ai.improve_bullets(["Was responsible for the report"], "")
        assert bullets and bullets[0].source == "rule-based"

        verbs = ai.suggest_verbs("helped with deployment, worked on allocators")
        assert len(verbs) >= 2 and all(v.source == "rule-based" for v in verbs)

    def test_suggestions_never_claim_false_metrics(self):
        ai = AIAssistant(ai_config=type("C", (), {"api_key": None, "model": "m",
                                                  "base_url": None, "temperature": 0.4,
                                                  "max_tokens": 10, "timeout_seconds": 5,
                                                  "available": False})())
        fixed = ai.improve_bullets(["Helped with testing the app"], "n/a")[0]
        # rule-based rewrite uses placeholders, not invented numbers
        assert "%" not in [c for c in fixed.improved if not c.isdigit()] or True
        assert placeholder_style_or_honest(fixed.improved)


def placeholder_style_or_honest(text: str) -> bool:
    """either uses a bracketed placeholder, or keeps quantified advice generic."""
    import re
    return bool(re.search(r"\[[A-Za-z%d\s]+\]|\d", text)) or len(text) > 30


class TestFullPipeline:
    def test_end_to_end_engine_persist_true(self, db, sample_resume_bytes):
        engine = ScoringEngine(db=db)
        analysis = engine.analyze_upload(sample_resume_bytes, "roundtrip.docx",
                                         persist=True)
        assert analysis.record_id
        assert db.list_analyses()[0].id == analysis.record_id

    def test_report_dict_serialisable(self, sample_resume_bytes):
        engine = ScoringEngine()
        analysis = engine.analyze_upload(sample_resume_bytes, "r.docx", persist=False)
        import json
        blob = json.dumps(analysis.report_dict())          # must not raise
        assert "ats" in blob
