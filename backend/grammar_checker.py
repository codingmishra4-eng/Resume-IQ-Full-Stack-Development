"""
Rule-based writing-quality checker.

Detect (with evidence, not vibes):
  - likely spelling mistakes (curated misspelling map + simple heuristics)
  - repeated consecutive words ("responsible responsible")
  - double spaces / stray whitespace patterns
  - weak action verbs ("worked on", "helped with", "responsible for")
  - very long sentences (readability flag)
  - passive-voice hints (was/were + past participle + 'by') — heuristic
  - overused buzzwords

Every finding is listed as a *heuristic warning* with the exact text so the
user can verify it. No content is changed without user consent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

import config
from config import get_logger

logger = get_logger("grammar_checker")

# --- Curated misspellings: wrong -> right (lower-case keys) ----------------
MISSPELLINGS: dict[str, str] = {
    "recieve": "receive", "seperate": "separate", "acheive": "achieve",
    "accomodate": "accommodate", "adress": "address", "begginer": "beginner",
    "collaegue": "colleague", "commited": "committed", "congradulations": "congratulations",
    "definately": "definitely", "excellant": "excellent", "expereince": "experience",
    "familliar": "familiar", "finaly": "finally", "foriegn": "foreign",
    "gaurantee": "guarantee", "goverment": "government", "grammer": "grammar",
    "independent": "independent", "knowlege": "knowledge", "liason": "liaison",
    "maintainance": "maintenance", "managment": "management", "neccessary": "necessary",
    "notifcation": "notification", "occured": "occurred", "oppurtunity": "opportunity",
    "persue": "pursue", "posession": "possession", "profesionnal": "professional",
    "proffesional": "professional", "pronounciation": "pronunciation",
    "publically": "publicly", "reccomend": "recommend", "refered": "referred",
    "relevent": "relevant", "responsability": "responsibility", "resposible": "responsible",
    "rythm": "rhythm", "succesful": "successful", "succsessfull": "successful",
    "suprise": "surprise", "tommorow": "tomorrow", "truely": "truly",
    "untill": "until", "wich": "which", "wierd": "weird",
    "apreciate": "appreciate", "atention": "attention", "beleive": "believe", "calender": "calendar",
    "catagory": "category", "cirtified": "certified", "colaborated": "collaborated",
    "critera": "criteria", "develope": "develop", "desicion": "decision",
    "efficent": "efficient", "enterance": "entrance", "enviroment": "environment",
    "excecutive": "executive", "experiance": "experience", "facilites": "facilities",
    "fulfilling": "fulfilling", "independance": "independence", "innovvation": "innovation",
    "instution": "institution", "intrest": "interest", "inturnship": "internship",
    "jepordize": "jeopardize", "langauge": "language", "lexamples": "examples",
    "medioacre": "mediocre", "morgage": "mortgage", "negociate": "negotiate",
    "occassion": "occasion", "organizaton": "organization", "parliment": "parliament",
    "perfomance": "performance", "persistance": "persistence",
    "posibilities": "possibilities", "pracitical": "practical", "priviledge": "privilege",
    "probaly": "probably", "qualifiyng": "qualifying", "recieved": "received",
    "refrence": "reference", "resposibilities": "responsibilities",
    "seperately": "separately", "similarily": "similarly", "sincerly": "sincerely",
    "stong": "strong", "submited": "submitted", "succedded": "succeeded",
    "techhnologies": "technologies", "teh": "the", "theif": "thief",
    "thier": "their", "unkown": "unknown", "usefull": "useful",
    "visting": "visiting", "wether": "whether", "yeild": "yield",
}

# Words commonly misused that we flag as "verify manually" (no auto-fix).
AMBIGUOUS_WORDS = {"manger": "manager?", "form": "from?", "loose": "lose?", "than": "then?"}

# Weak/verbose verb phrases with suggested stronger alternatives.
WEAK_PHRASES: dict[str, str] = {
    "responsible for": "owned / led / managed",
    "worked on": "built / engineered / delivered",
    "helped with": "enabled / drove",
    "assisted in": "supported (specify your concrete contribution)",
    "involved in": "contributed to (state the outcome)",
    "participated in": "contributed to (state the outcome)",
    "helped to": "enabled",
    "in charge of": "led / managed",
    "took care of": "managed / owned",
    "duties included": "delivered (list outcomes)",
    "was a part of": "contributed to",
}

STRONG_VERB_SUGGESTIONS = ["built", "led", "launched", "designed", "automated",
                           "shipped", "optimized", "reduced", "grew", "negotiated"]

BUZZWORDS = ["hardworking", "team player", "go-getter", "results-driven",
             "think outside the box", "synergy", "self-motivated", "detail-oriented"]

FILLER_INTENSIFIERS = ["very", "really", "extremely", "basically", "actually",
                       "literally", "just", "totally"]

PASSIVE_RE = re.compile(r"\b(was|were|been|being|is|are)\b\s+(\w+ed|\w+en)\b", re.IGNORECASE)
REPEAT_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)


@dataclass
class Issue:
    """One writing-quality finding, with location evidence for the user."""

    kind: str            # 'spelling' | 'grammar' | 'weak_verb' | 'style' | ...
    message: str
    context: str         # the surrounding snippet so the user can locate it
    suggestion: str = ""

    def as_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message,
                "context": self.context, "suggestion": self.suggestion}


@dataclass
class WritingReport:
    findings: list[Issue] = field(default_factory=list)
    long_sentences: list[str] = field(default_factory=list)
    passive_count: int = 0
    buzzwords_found: list[str] = field(default_factory=list)
    repeated_words: list[tuple[str, int]] = field(default_factory=list)
    palavra_stats: dict = field(default_factory=dict)  # (kept generic for future)

    @property
    def spelling_issues(self) -> list[Issue]:
        return [f for f in self.findings if f.kind == "spelling"]

    @property
    def grammar_issues(self) -> list[Issue]:
        return [f for f in self.findings if f.kind == "grammar"]

    @property
    def weak_phrasings(self) -> list[Issue]:
        return [f for f in self.findings if f.kind == "weak_verb"]


def _contexts_for(pattern: re.Pattern, text: str, width: int = 60, limit: int = 25) -> Iterable[re.Match]:
    """Yield matches (bounded) for a pattern with contextual snippets."""
    count = 0
    for m in pattern.finditer(text):
        yield m
        count += 1
        if count >= limit:
            break


class GrammarChecker:
    """Heuristic writing-quality checks over resume text."""

    def check(self, text: str) -> WritingReport:
        report = WritingReport()
        if not text or not text.strip():
            return report

        lower = text.lower()

        self._spellings(text, report)
        self._repeats(text, report)
        self._weak_phrases(lower, text, report)
        self._passive_and_sentences(text, report)
        self._buzzwords(lower, report)
        self._spacing(text, report)
        return report

    # -- individual checks ---------------------------------------------------

    def _spellings(self, text: str, report: WritingReport) -> None:
        found: set[str] = set()
        tokens = re.findall(r"[A-Za-z][a-zA-Z']+", text)
        for tok in tokens:
            low = tok.lower()
            if low in found:
                continue
            if low in MISSPELLINGS:
                found.add(low)
                report.findings.append(Issue(
                    kind="spelling",
                    message=f"Likely misspelling: “{tok}”",
                    suggestion=MISSPELLINGS[low],
                    context=_match_context(text, tok)))
            elif low in AMBIGUOUS_WORDS and not re.match(r"^[A-Z]", tok):
                found.add(low)
                report.findings.append(Issue(
                    kind="spelling",
                    message=f"Verify word usage: “{tok}”",
                    suggestion=AMBIGUOUS_WORDS[low],
                    context=_match_context(text, tok)))

    def _repeats(self, text: str, report: WritingReport) -> None:
        for m in REPEAT_RE.finditer(text):
            word = m.group(1).lower()
            if word in {"that", "had"}:      # legitimate repeats
                continue
            report.findings.append(Issue(
                kind="grammar",
                message=f"Repeated word: “{m.group(1)} … {m.group(1)}”",
                suggestion="Remove one of the duplicates.",
                context=_match_context(text, m.group(0))))

        counts: dict[str, int] = {}
        for tok in re.findall(r"[a-z]{4,}", text.lower()):
            counts[tok] = counts.get(tok, 0) + 1
        overused = sorted(((w, c) for w, c in counts.items() if c >= 6), key=lambda x: -x[1])[:8]
        report.repeated_words = overused

    def _weak_phrases(self, lower: str, original: str, report: WritingReport) -> None:
        for phrase, better in WEAK_PHRASES.items():
            for m in _contexts_for(re.compile(re.escape(phrase)), lower):
                report.findings.append(Issue(
                    kind="weak_verb",
                    message=f"Weak phrasing: “{phrase}”",
                    suggestion=f"Stronger alternative: {better}",
                    context=_match_context(original, phrase)))

    def _passive_and_sentences(self, text: str, report: WritingReport) -> None:
        report.passive_count = len(PASSIVE_RE.findall(text))
        # Sentence length via simple splitter (spaCy is optional, used by UI.)
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        report.long_sentences = [
            s.strip() for s in sentences
            if len(s.split()) > 34 and len(s.strip()) > 40
        ][:10]

    def _buzzwords(self, lower: str, report: WritingReport) -> None:
        found = [b for b in BUZZWORDS if b in lower]
        report.buzzwords_found = found

    def _spacing(self, text: str, report: WritingReport) -> None:
        if "  " in text.replace("\t", ""):
            report.findings.append(Issue(
                kind="style",
                message="Double spaces detected.",
                suggestion="Use single spaces after periods/commas.",
                context="Throughout the document"))


def _match_context(text: str, needle: str, radius: int = 30) -> str:
    """Return a short ±radius snippet around the first occurrence of needle."""
    idx = text.lower().find(needle.lower())
    if idx == -1:
        return ""
    start, end = max(0, idx - radius), min(len(text), idx + len(needle) + radius)
    return ("…" if start > 0 else "") + text[start:end].replace("\n", " ") + ("…" if end < len(text) else "")
