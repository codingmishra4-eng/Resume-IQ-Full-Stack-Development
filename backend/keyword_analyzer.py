"""
Keyword & skill analysis.

Maintains a curated taxonomy of ~250 real-world skills/keywords grouped by
domain, extracts which ones appear in a resume or job description, and
computes coverage. This is pattern matching against actual text — never
invented results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Skill taxonomy ---------------------------------------------------------
# Structure: category -> list of canonical skill names. Matching is
# case-insensitive substring/word matching; a few skills use regex forms.

SKILL_TAXONOMY: dict[str, list[str]] = {
    "Programming": ["python", "java", "c++", "c#", "javascript", "typescript",
                    "go", "golang", "rust", "kotlin", "swift", "php", "ruby",
                    "scala", "r programming", "matlab", "sql", "pl/sql"],
    "Web & Frontend": ["html", "css", "sass", "react", "redux", "next.js",
                       "vue.js", "angular", "tailwind", "bootstrap",
                       "responsive design", "web accessibility", "webpack"],
    "Backend & APIs": ["node.js", "express", "django", "flask", "fastapi",
                       "spring boot", "asp.net", "rest api", "graphql",
                       "microservices", "oauth", "jwt", "redis", "rabbitmq", "kafka"],
    "Databases": ["mysql", "postgresql", "mongodb", "firebase", "dynamodb",
                  "oracle", "sqlite", "elasticsearch", "data modeling", "indexing"],
    "Cloud & DevOps": ["aws", "azure", "gcp", "google cloud", "docker",
                       "kubernetes", "terraform", "jenkins", "ci/cd",
                       "git", "github actions", "linux", "ansible", "monitoring"],
    "Data Science & ML": ["machine learning", "deep learning", "neural networks",
                          "nlp", "computer vision", "pandas", "numpy", "scikit-learn",
                          "tensorflow", "pytorch", "keras", "statistics",
                          "data analysis", "data visualization", "tableau",
                          "power bi", "excel", "spss", "a/b testing", "etl",
                          "spark", "hadoop", "feature engineering"],
    "Mobile": ["android", "ios", "flutter", "react native", "xamarin"],
    "QA & Testing": ["unit testing", "integration testing", "pytest", "junit",
                     "selenium", "cypress", "test automation", "manual testing", "jira"],
    "Business & PM": ["project management", "agile", "scrum", "kanban",
                      "stakeholder management", "roadmap", "backlog",
                      "kpi", "business analysis", "requirements gathering",
                      "user stories", "process improvement", "market research"],
    "Design & UX": ["figma", "adobe xd", "sketch", "user research", "wireframing",
                    "prototyping", "usability testing", "design systems",
                    "typography", "personas", "information architecture"],
    "Soft Skills": ["communication", "teamwork", "leadership", "problem solving",
                    "time management", "adaptability", "presentation",
                    "collaboration", "critical thinking", "mentoring", "ownership"],
    "General Professional": ["microsoft office", "powerpoint", "microsoft word",
                             "google workspace", "crm", "erp", "sap", "salesforce",
                             "data entry", "reporting", "documentation", "email marketing", "seo"],
}

# Flatten once — a dict pointing category lookup for a normalised skill name.
_SKILL_LOOKUP: dict[str, tuple[str, str]] = {}
for _category, _skills in SKILL_TAXONOMY.items():
    for _skill in _skills:
        _SKILL_LOOKUP[_skill.lower()] = (_category, _skill)


@dataclass
class KeywordReport:
    """Result of keyword coverage for one piece of text."""

    matched: dict[str, list[str]] = field(default_factory=dict)          # category -> skills
    total_matched: int = 0
    density: float = 0.0            # matched per 100 words
    action_verbs_found: list[str] = field(default_factory=list)
    overused_terms: list[tuple[str, int]] = field(default_factory=list)

    @property
    def all_matched(self) -> list[str]:
        return [s for skills in self.matched.values() for s in skills]

    @property
    def matched_count(self) -> int:
        return self.total_matched


ACTION_VERBS = {"built", "led", "managed", "designed", "developed", "created",
                "implemented", "launched", "improved", "reduced", "increased",
                "automated", "optimized", "analysed", "analyzed", "delivered",
                "shipped", "maintained", "migrated", "mentored", "negotiated",
                "organized", "spearheaded", "streamlined", "tested", "owned",
                "engineered", "collaborated", "coordinated", "drove", "grew",
                "achieved", "accelerated", "architected", "counseled", "debugged"}


class KeywordAnalyzer:
    """Extracts skill/keyword evidence from resume or job-description text."""

    def __init__(self, taxonomy: dict[str, list[str]] | None = None):
        self.taxonomy = taxonomy or SKILL_TAXONOMY

    def analyze(self, text: str) -> KeywordReport:
        """Match taxonomy skills against raw text; report density & verbs."""
        report = KeywordReport()
        if not text:
            return report

        haystack = text.lower()
        words = re.findall(r"[a-z0-9+#./-]+", haystack)
        total_words = max(len(words), 1)

        matched_count = 0
        for skill in _SKILL_LOOKUP:
            if re.search(r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])", haystack):
                category, display = _SKILL_LOOKUP[skill]
                bucket = report.matched.setdefault(category, [])
                if display not in bucket:
                    bucket.append(display)
                    matched_count += 1

        report.total_matched = matched_count
        report.density = round(100 * matched_count / total_words, 2)

        for verb in ACTION_VERBS:
            if re.search(r"(?<![a-z])" + verb + r"(?![a-z])", haystack):
                report.action_verbs_found.append(verb)
        report.action_verbs_found.sort()

        counts: dict[str, int] = {}
        for tok in re.findall(r"[a-z]{5,}", haystack):
            counts[tok] = counts.get(tok, 0) + 1
        report.overused_terms = sorted(((w, c) for w, c in counts.items() if c >= 8), key=lambda x: -x[1])[:8]
        return report

    # ---------------------------------------------------------------------

    def extract_jd_requirements(self, jd_text: str) -> dict[str, list[str]]:
        """Which taxonomy skills the *job description* asks for."""
        rep = self.analyze(jd_text)
        return rep.matched

    def coverage_against(self, jd_text: str, resume_text: str) -> dict[str, list[str] | None]:
        """Return {'matching', 'partial', 'missing'} skill lists for a JD vs resume."""
        jd_report = self.analyze(jd_text.lower())
        res_report = self.analyze(resume_text.lower())
        jd_skills = [s for list_ in jd_report.matched.values() for s in list_]
        res_skills = {s.lower() for s in res_report.all_matched}

        matching: list[str] = []
        missing: list[str] = []
        for skill in jd_skills:
            if skill.lower() in res_skills:
                matching.append(skill)
            else:
                missing.append(skill)
        return {"matching": matching, "partial": [], "missing": missing}
