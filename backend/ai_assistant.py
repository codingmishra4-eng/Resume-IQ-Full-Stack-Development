"""
AI resume improvement assistant.

Pattern: `AIAssistant` tries the OpenAI API when a key is configured; every
method has a deterministic, rule-based fallback so the app stays fully usable
(and honest) without the key. Results always carry `source: "openai"` or
`source: "rule-based"` so the UI can label where a suggestion came from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import config
from config import get_logger, AIConfig

logger = get_logger("ai_assistant")


@dataclass
class AISuggestion:
    """One actionable improvement the user can accept / edit / reject."""

    kind: str                      # 'summary' | 'bullet' | 'phrasing' | 'keyword' | ...
    original: str
    improved: str
    rationale: str
    source: str = "rule-based"     # vernable provenance — shown in UI

    def as_dict(self) -> dict:
        return {"kind": self.kind, "original": self.original,
                "improved": self.improved, "rationale": self.rationale, "source": self.source}


@dataclass
class SuggestionBundle:
    """All AI/rule-generated suggestions for one session."""

    items: list[AISuggestion] = field(default_factory=list)
    ai_available: bool = False

    @property
    def by_kind(self) -> dict[str, list[AISuggestion]]:
        out: dict[str, list[AISuggestion]] = {}
        for s in self.items:
            out.setdefault(s.kind, []).append(s)
        return out


class AIAssistant:
    """OpenAI-backed assistant with an honest rule-based fallback."""

    def __init__(self, ai_config: AIConfig | None = None):
        self.cfg = ai_config or config.AIConfig()
        self._client = None
        self.ai_available = False
        if self.cfg.available:
            try:
                import openai                                        # optional dep
                self._client = openai.OpenAI(
                    api_key=self.cfg.api_key,
                    base_url=self.cfg.base_url or None,
                    timeout=self.cfg.timeout_seconds,
                )
                self.ai_available = True
                logger.info("OpenAI assistant initialised (model=%s)", self.cfg.model)
            except Exception as exc:                                 # noqa: BLE001
                logger.warning("OpenAI init failed, falling back to rules: %s", type(exc).__name__)
        else:
            logger.info("No OPENAI_API_KEY — using rule-based fallback everywhere.")

    # ------------------------------------------------------------------ #
    def _chat(self, system: str, user: str) -> str | None:
        """Call the API; return text or None on any failure (never raises)."""
        if not self.ai_available:
            return None
        try:
            resp = self._client.chat.completions.create(                 # type: ignore[union-attr]
                model=self.cfg.model,
                temperature=self.cfg.temperature,
                max_tokens=self.cfg.max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or None
        except Exception as exc:                                         # noqa: BLE001
            logger.warning("OpenAI call failed: %s", type(exc).__name__)
            return None

    # ---------------------------- features ------------------------------ #

    def rewrite_summary(self, summary: str, resume_text: str,
                        role: str = "") -> AISuggestion:
        """Rewrite a professional summary; falls back to a rule-based rewrite."""
        system = ("You are a professional resume writer. Rewrite resume professional "
                  "summaries. Never invent employers, titles, dates, numbers, or skills "
                  "that are not supported by the resume text. If a metric would help, use "
                  "a bracketed placeholder like [X%].")
        user = (f"Role: {role or 'unspecified'}\n\n"
                f"Current summary:\n{summary or '(none — write one)'}\n\n"
                f"Resume text (grounding, truncated):\n{resume_text[:3500]}")
        text = self._chat(system, user)
        if text:
            return AISuggestion(kind="summary", original=summary or "",
                                improved=text, source="openai",
                                rationale="AI rewrite grounded in your resume content.")

        # Rule-based fallback: assemble a factual, metric-placeholder summary.
        improved = self._rule_summary(summary, resume_text, role)
        return AISuggestion(kind="summary", original=summary or "",
                            improved=improved, source="rule-based",
                            rationale="Rule-based template using details already in your resume.")

    def _rule_summary(self, summary: str, resume_text: str, role: str) -> str:
        import re as _re
        # Best-effort title detection so the rewrite talks about the user's actual
        # domain instead of a generic placeholder.
        titles = ["data analyst", "data scientist", "business analyst", "software engineer",
                  "web developer", "frontend developer", "backend developer", "full stack developer",
                  "product manager", "project manager", "marketing analyst", "sales associate",
                  "ui/ux designer", "graphic designer", "devops engineer", "qa engineer",
                  "machine learning engineer", "financial analyst", "accountant",
                  "hr recruiter", "customer support", "operations manager", "data engineer",
                  "systems engineer", "network engineer", "bi developer", "intern"]
        low = resume_text.lower()
        if not role:
            for t in titles:
                if t in low:
                    role = t.title()
                    break
        skills = self._top_skills(resume_text)
        display_skills = [s.title() if len(s) > 3 else s.upper() for s in skills]
        role_line = role or "your target role"
        return (
            f"{role_line} with hands-on experience in {', '.join(display_skills[:4])}. "
            f"Proven record of delivering measurable outcomes — quantify one here, e.g. "
            f"\"[X%] improvement / [N] users served / [T hours] saved\". "
            f"Known strengths include collaboration and ownership of end-to-end delivery."
        )

    def improve_bullets(self, bullets: list[str], resume_text: str) -> list[AISuggestion]:
        """Rewrite weak bullet points with before/after comparisons."""
        out: list[AISuggestion] = []
        weak = [b for b in bullets if self._is_weak_bullet(b)]
        targets = weak[:6] or bullets[:4]

        if self.ai_available:
            system = ("You are an ATS-aware resume writer. Rewrite resume bullets to be "
                      "concise (max 2 lines), start with a strong action verb, and end "
                      "with an outcome. NEVER invent metrics — use placeholders like "
                      "[X%] or [N users] where a number is missing. Return ONLY JSON: "
                      '{"items": [{"original": "...", "improved": "...", "rationale": "..."}]}.')
            user = "Bullets:\n" + "\n".join(f"- {b}" for b in targets)
            text = self._chat(system, user)
            if text:
                parsed = self._parse_json_items(text)
                for item in parsed:
                    out.append(AISuggestion(kind="bullet", original=item.get("original", ""),
                                            improved=item.get("improved", ""),
                                            rationale=item.get("rationale", ""),
                                            source="openai"))
        if not out:
            out.extend(self._rule_fix_bullets(targets))
        return out

    def _rule_fix_bullets(self, targets: list[str]) -> list[AISuggestion]:
        """Deterministic bullet rewrites — no API needed, no invented facts."""
        import re as _re
        from backend.grammar_checker import WEAK_PHRASES
        # Passive-voice variants need a finite replacement ("was responsible for"
        # → "was owned reporting" is broken English; "led" reads naturally).
        extended = {
            "was responsible for": "led",
            "were responsible for": "led",
            "am responsible for": "lead",
            "is responsible for": "leads",
            "was in charge of": "led",
            "were in charge of": "led",
        }
        suggestions: list[AISuggestion] = []
        for b in targets:
            improved = b
            swapped = None
            lowered = b.lower()
            for phrase, better in {**extended, **WEAK_PHRASES}.items():
                pos = lowered.find(phrase)
                if pos != -1:
                    # Use the first strong verb listed in the suggestion.
                    strong = better.split(" /")[0].split(" (")[0].strip()
                    improved = b[:pos] + strong + " " + b[pos + len(phrase):]
                    improved = improved.strip()
                    improved = _re.sub(r"  +", " ", improved)
                    improved = improved[0].upper() + improved[1:]
                    swapped = phrase
                    break
            if not _re.search(r"\d", improved):
                improved = improved.rstrip(" .") + \
                    " — quantify the impact (e.g. “reduced [X%]” or “saved [N hours]/week”)."
            reason = (f"Replaced weak phrase “{swapped}” with a stronger verb."
                      if swapped else "Shortened and re-anchored; add a real metric where flagged.")
            suggestions.append(AISuggestion(kind="bullet", original=b, improved=improved,
                                            source="rule-based", rationale=reason))
        return suggestions

    def suggest_verbs(self, text: str) -> list[AISuggestion]:
        """Suggest stronger action verbs for weak verb usages found."""
        from backend.grammar_checker import WEAK_PHRASES
        out: list[AISuggestion] = []
        lowered = text.lower()
        for phrase, better in WEAK_PHRASES.items():
            if phrase in lowered and len(out) < 10:
                out.append(AISuggestion(kind="phrasing", original=phrase, improved=better,
                                        source="rule-based",
                                        rationale=f"“{phrase}” under-sells the work; prefer direction and outcome."))
        return out

    def keyword_guidance(self, missing_skills: list[str], jd_text: str,
                         resume_text: str) -> AISuggestion:
        """Advice for incorporating missing JD keywords *naturally*."""
        system = ("Act as an ATS keyword coach. Using ONLY the skills listed, draft 2-3 "
                  "example resume bullets showing how to weave missing skills in naturally. "
                  "Do not claim the candidate already used these skills in past jobs unless "
                  "the resume shows it. Keep claims truthful and generic enough to edit.")
        user = (f"Missing skills: {', '.join(missing_skills[:12])}\n\n"
                f"Job description snippet:\n{jd_text[:1500]}")
        text = self._chat(system, user)
        if text:
            return AISuggestion(kind="keyword", original=", ".join(missing_skills[:12]),
                                improved=text, source="openai",
                                rationale="AI-generated weaving examples; edit before use.")
        joined = ", ".join(missing_skills[:10]) or "the listed skills"
        return AISuggestion(
            kind="keyword",
            original=", ".join(missing_skills[:12]),
            improved=("Add a truthful line like: ”Currently strengthening my {X} skills via "
                      f"[course/project], applying them in [project] (outcome: [metric]).” "
                      f"Write bullets in your • Experience/Projects sections where {joined} "
                      "plausibly apply — for real experience only."),
            source="rule-based",
            rationale="Rule-based guidance: place genuine skills in bullets with real outcomes.")

    # ----------------------------- helpers ------------------------------ #

    def _top_skills(self, resume_text: str) -> list[str]:
        from backend.keyword_analyzer import KeywordAnalyzer
        rep = KeywordAnalyzer().analyze(resume_text or "")
        return rep.all_matched

    @staticmethod
    def _is_strong_start(low: str) -> bool:
        """True when a (lowercased) line starts with a strong action verb."""
        return low.startswith(("built", "led", "designed", "developed", "created",
                               "implemented", "launched", "managed", "owned", "drove",
                               "automated", "engineered", "delivered", "shipped",
                               "reduced", "increased", "improved", "optimized", "grew"))

    @staticmethod
    def _is_weak_bullet(b: str) -> bool:
        low = b.lower()
        if len(b.split()) > 32:
            return True
        if not AIAssistant._is_strong_start(low):
            return True
        from backend.grammar_checker import WEAK_PHRASES
        for p in WEAK_PHRASES:
            if p in low:
                return True
        return False

    @staticmethod
    def _parse_json_items(text: str) -> list[dict]:
        """Best-effort JSON extraction from an LLM reply (never raises)."""
        try:
            data = json.loads(text)
            return list(data.get("items", [])) if isinstance(data, dict) else []
        except ValueError:
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    return list(data.get("items", [])) if isinstance(data, dict) else []
                except ValueError:
                    return []
        return []
