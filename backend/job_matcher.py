"""
Job-description ↔ resume matching.

Approach (transparent & data-driven):
1. Extract taxonomy skills the JD asks for.
2. Extract extra keywords from the JD (running text, excluding stop words).
3. Match against the resume: exact skill hit, rule-based partial (related
   category skills / substring), or missing.
4. Compute a match % weighted by skills (70%) + general keyword coverage (30%).

Never fabricates: every displayed skill is literally found in one of the texts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.keyword_analyzer import SKILL_TAXONOMY, KeywordAnalyzer
from backend.resume_parser import ParsedResume

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "in", "on", "for", "with", "of", "at",
    "by", "from", "as", "is", "are", "be", "been", "will", "we", "our", "you",
    "your", "their", "this", "that", "role", "work", "working", "job", "team",
    "company", "candidate", "experience", "years", "year", "strong", "good",
    "have", "has", "must", "should", "can", "ability", "skills", "skill",
    "including", "using", "well", "other", "new", "within", "across", "more",
    "than", "also", "such", "who", "what", "plus", "via", "all", "not", "it",
}

TITLE_RE = re.compile(r"^\s*(job\s*title|position|role)\s*[:-]?\s*(.+)$", re.IGNORECASE | re.MULTILINE)
EXPERIENCE_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:to\s*(\d{1,2})\s*)?(?:years?)", re.IGNORECASE)
DEGREE_RE = re.compile(
    r"\b(b\.?tech|b\.?e\.?|b\.?sc|bachelor'?s?|master'?s?|m\.?tech|m\.?sc|mba|ph\.?d|phd|diploma)\b",
    re.IGNORECASE)


@dataclass
class JobMatchResult:
    """Everything the Job Match tab needs to render."""

    job_title: str = ""
    match_score: float = 0.0
    matching: list[str] = field(default_factory=list)     # exact skill hits
    partial: list[str] = field(default_factory=list)      # related-category hits
    missing: list[str] = field(default_factory=list)      # JD skills absent in resume
    jd_extra_keywords: list[str] = field(default_factory=list)   # non-taxonomy JD terms
    resume_categories: dict[str, list[str]] = field(default_factory=dict)
    jd_categories: dict[str, list[str]] = field(default_factory=dict)
    min_years: tuple[int, int] | None = None              # (min, max) from JD
    degree_requirements: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "job_title": self.job_title, "match_score": self.match_score,
            "matching": self.matching, "partial": self.partial, "missing": self.missing,
            "jd_extra_keywords": self.jd_extra_keywords,
            "resume_categories": self.resume_categories,
            "jd_categories": self.jd_categories,
            "min_years": self.min_years, "degrees": self.degree_requirements,
            "notes": self.notes,
        }


class JobMatcher:
    """Compare a ParsedResume against a pasted/uploaded job description."""

    def __init__(self, keyword_analyzer: KeywordAnalyzer | None = None):
        self.keywords = keyword_analyzer or KeywordAnalyzer()

    # ------------------------------------------------------------------ #
    def match(self, resume: ParsedResume, jd_text: str) -> JobMatchResult:
        result = JobMatchResult()
        if not jd_text or not jd_text.strip():
            result.notes.append("No job description provided.")
            return result
        if len(jd_text.strip().split()) < 15:
            result.notes.append("The job description looks too short — paste the full "
                                "description for a reliable match.")

        jd_lower = jd_text.lower()
        resume_text = resume.text.lower()

        # --- metadata ------------------------------------------------------
        m = TITLE_RE.search(jd_text)
        result.job_title = (m.group(2).strip() if m else "")[:120]
        years = EXPERIENCE_YEARS_RE.findall(jd_lower)
        if years:
            lo = min(int(a) for a, _ in years if a)
            ups = [int(b) for _, b in years if b]
            result.min_years = (lo, max(ups) if ups else lo)
            if result.min_years[0] > 2:
                result.notes.append(
                    f"JD asks for ~{result.min_years[0]}+ years. Only mention experience you actually have.")
        result.degree_requirements = list(dict.fromkeys(d.lower() for d in DEGREE_RE.findall(jd_lower)))[:5]

        # --- skill set matching ---------------------------------------------
        jd_cats: dict[str, list[str]] = {}
        for category, skills in SKILL_TAXONOMY.items():
            for skill in skills:
                if re.search(r"(?<![a-z])" + re.escape(skill.lower()) + r"(?![a-z])", jd_lower):
                    jd_cats.setdefault(category, []).append(skill)

        res_cats: dict[str, list[str]] = {}
        for category, skills in SKILL_TAXONOMY.items():
            for skill in skills:
                if re.search(r"(?<![a-z])" + re.escape(skill.lower()) + r"(?![a-z])", resume_text):
                    res_cats.setdefault(category, []).append(skill)

        jd_skills = [s for lst in jd_cats.values() for s in lst]
        res_skills = {s for lst in res_cats.values() for s in lst}

        matching, partial, missing = [], [], []
        jd_cat_of = {s: c for c, lst in jd_cats.items() for s in lst}
        for skill in jd_skills:
            if skill in res_skills:
                matching.append(skill)
                continue
            # Partial: resume shows OTHER skills in the same domain category.
            category = jd_cat_of[skill]
            if any(rc in res_skills for rc in jd_cats.get(category, [])):
                partial.append(skill)
            else:
                missing.append(skill)

        result.matching = sorted(set(matching), key=str.lower)
        result.partial = sorted(set(partial) - set(result.matching), key=str.lower)
        result.missing = sorted(set(missing), key=str.lower)
        result.jd_categories = jd_cats
        result.resume_categories = res_cats

        # --- extra JD keywords (non-taxonomy) -------------------------------
        jd_tokens = [t for t in re.findall(r"[a-z][a-z+#./-]{3,}", jd_lower) if t not in STOP_WORDS]
        freq: dict[str, int] = {}
        for tok in jd_tokens:
            freq[tok] = freq.get(tok, 0) + 1
        common_terms = [t for t, c in sorted(freq.items(), key=lambda x: -x[1])
                        if c >= 2 and t not in jd_skills and len(t) > 3][:25]
        result.jd_extra_keywords = [t for t in common_terms if t not in resume_text][:15]

        # --- match % ---------------------------------------------------------
        skill_n = len(jd_skills) or 1
        skill_score = (len(result.matching) + 0.5 * len(result.partial)) / skill_n

        res_top = {t for lst in res_cats.values() for t in lst}
        extra_coverage = (len([t for t in common_terms if t in resume_text]) / max(len(common_terms), 1)) \
            if common_terms else None
        if extra_coverage is None:
            total = skill_score
        else:
            total = 0.70 * skill_score + 0.30 * extra_coverage

        result.match_score = round(100 * min(total, 1.0), 1)

        # --- recommendations text -------------------------------------------
        if result.missing:
            result.notes.append(
                f"{len(result.missing)} skills the JD mentions do not appear in your resume. "
                "Add the ones you genuinely have; do NOT list skills you don't know.")
        if result.partial:
            result.notes.append(
                "Partially matched skills: your resume shows related same-domain skills but not the "
                "exact terms — use the JD's exact terminology where it is truthful.")
        if result.jd_extra_keywords:
            result.notes.append(
                "Job-specific vocabulary worth weaving in naturally: "
                + ", ".join(result.jd_extra_keywords[:8]) + ".")
        return result
