"""
Grammar checker tests — known misspellings, repeats, weak verbs.
"""

from __future__ import annotations

from backend.grammar_checker import GrammarChecker


class TestGrammar:
    def test_detects_misspelling(self):
        report = GrammarChecker().check("Experiance with Python and SQL colaborated with teams.")
        messages = [f.message for f in report.spelling_issues]
        assert any("experiance" in m.lower() for m in messages)
        assert any("colaborated" in m.lower() for m in messages)

    def test_correct_text_is_clean(self):
        report = GrammarChecker().check(
            "Built a data pipeline with Python and SQL, reducing load time by 40%.")
        assert report.spelling_issues == []

    def test_repeated_word(self):
        report = GrammarChecker().check("Managed a team team of six engineers in Bengaluru.")
        assert any("Repeated word" in f.message for f in report.grammar_issues)

    def test_weak_phrases(self):
        report = GrammarChecker().check("Was responsible for the deployment pipeline.")
        assert any("responsible for" in f.message.lower() for f in report.weak_phrasings)

    def test_long_sentence_flagged(self):
        long = " ".join(["word"] * 40)
        report = GrammarChecker().check(long)
        assert report.long_sentences

    def test_empty_input_safe(self):
        report = GrammarChecker().check("   \n  ")
        assert report.findings == []
