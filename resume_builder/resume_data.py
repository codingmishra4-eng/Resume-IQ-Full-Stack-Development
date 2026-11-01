"""
Resume data model for the builder.

A resume is plain nested data (dicts/lists) so it serialises directly to the
database JSON column. `ResumeData` offers typed access plus helpers used by
every generator (PDF, DOCX, HTML preview).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import re


def _clean(text: str | None) -> str:
    """Collapse whitespace/newlines for storage-safe rendering."""
    if not text:
        return ""
    return re.sub(r"[ \t]+", " ", str(text)).strip()


@dataclass
class ExperienceItem:
    role: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class EducationItem:
    degree: str = ""
    institution: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    details: str = ""


@dataclass
class ProjectItem:
    name: str = ""
    tech: str = ""
    description: str = ""
    link: str = ""


@dataclass
class CertificationItem:
    name: str = ""
    issuer: str = ""
    year: str = ""


@dataclass
class LanguageItem:
    name: str = ""
    level: str = ""


@dataclass
class ResumeData:
    """Complete, editable resume content."""

    # identity
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""

    # content sections
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[ExperienceItem] = field(default_factory=list)
    education: list[EducationItem] = field(default_factory=list)
    projects: list[ProjectItem] = field(default_factory=list)
    certifications: list[CertificationItem] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    languages: list[LanguageItem] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)

    # additional free-form sections the user may add: {"title": ..., "body": ...}
    extra_sections: list[dict[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResumeData":
        """Load a ResumeData from a DB/UI JSON payload (defensive defaults)."""
        src = data or {}
        values: dict[str, Any] = {}
        str_fields = {"full_name", "headline", "email", "phone", "location",
                      "linkedin", "github", "website", "summary"}
        for f in str_fields:
            values[f] = _clean(src.get(f, ""))

        values["skills"] = [_clean(str(s)) for s in (src.get("skills") or []) if _clean(str(s))]
        values["achievements"] = [_clean(str(a)) for a in (src.get("achievements") or []) if _clean(str(a))]
        values["interests"] = [_clean(str(i)) for i in (src.get("interests") or []) if _clean(str(i))]

        values["experience"] = [ExperienceItem(
            role=_clean(e.get("role")), company=_clean(e.get("company")),
            location=_clean(e.get("location")), start=_clean(e.get("start")),
            end=_clean(e.get("end")),
            bullets=[_clean(b) for b in (e.get("bullets") or []) if _clean(b)],
        ) for e in (src.get("experience") or [])]

        values["education"] = [EducationItem(
            degree=_clean(d.get("degree")), institution=_clean(d.get("institution")),
            location=_clean(d.get("location")), start=_clean(d.get("start")),
            end=_clean(d.get("end")), details=_clean(d.get("details")),
        ) for d in (src.get("education") or [])]

        values["projects"] = [ProjectItem(
            name=_clean(p.get("name")), tech=_clean(p.get("tech")),
            description=_clean(p.get("description")), link=_clean(p.get("link")),
        ) for p in (src.get("projects") or [])]

        values["certifications"] = [CertificationItem(
            name=_clean(c.get("name")), issuer=_clean(c.get("issuer")), year=_clean(c.get("year")),
        ) for c in (src.get("certifications") or [])]

        values["languages"] = [LanguageItem(name=_clean(l.get("name")), level=_clean(l.get("level")))
                               for l in (src.get("languages") or [])]

        values["extra_sections"] = [
            {"title": _clean(s.get("title"), ), "body": _clean(s.get("body"))}
            for s in (src.get("extra_sections") or [])
            if _clean(s.get("title"))
        ]
        return cls(**values)

    # ------------------------------------------------------------------ #
    def contact_items(self) -> list[str]:
        """Rendered contact chips, in display order, skipping empties."""
        items = [self.email, self.phone, self.location]
        items.extend(x for x in (self.linkedin, self.github, self.website) if x)
        return [i for i in items if i]

    def has_content(self) -> bool:
        """Does the resume contain anything meaningful yet?"""
        return any([
            self.full_name, self.summary, self.skills, self.experience,
            self.education, self.projects, self.certifications,
            self.achievements, self.languages, self.interests, self.extra_sections,
        ])

    def as_plain_text(self) -> str:
        """Flat ATS-style text render — used by builders' analysis hooks."""
        lines: list[str] = []
        if self.full_name:
            lines.append(self.full_name)
        if self.headline:
            lines.append(self.headline)
        lines.append(" | ".join(self.contact_items()))
        if self.summary:
            lines.append("\nSUMMARY\n" + self.summary)

        if self.experience:
            lines.append("\nWORK EXPERIENCE")
            for e in self.experience:
                lines.append(f"{e.role} — {e.company} ({e.start}–{e.end})")
                lines.extend(f"- {b}" for b in e.bullets)

        if self.education:
            lines.append("\nEDUCATION")
            lines.extend(f"{d.degree}, {d.institution} ({d.start}–{d.end})" for d in self.education)

        if self.skills:
            lines.append("\nSKILLS\n" + ", ".join(self.skills))
        if self.projects:
            lines.append("\nPROJECTS")
            for p in self.projects:
                lines.append(f"- {p.name} ({p.tech}): {p.description}")
        if self.certifications:
            lines.append("\nCERTIFICATIONS")
            lines.extend(f"- {c.name} — {c.issuer} ({c.year})" for c in self.certifications)
        if self.achievements:
            lines.append("\nACHIEVEMENTS\n" + "\n".join(f"- {a}" for a in self.achievements))
        if self.languages:
            lines.append("\nLANGUAGES\n" + ", ".join(f"{l.name} ({l.level})" for l in self.languages))
        if self.interests:
            lines.append("\nINTERESTS\n" + ", ".join(self.interests))
        for s in self.extra_sections:
            lines.append(f"\n{s['title'].upper()}\n{s['body']}")
        return "\n".join(lines)

    def completeness(self) -> tuple[float, list[str]]:
        """(percent, missing_section_labels) — powers the builder's quality meter."""
        missing: list[str] = []
        if not self.full_name:
            missing.append("Your name")
        if not self.summary:
            missing.append("Professional summary")
        if not self.experience and not self.projects:
            missing.append("Experience or projects")
        if not self.education:
            missing.append("Education")
        if not self.skills:
            missing.append("Skills")
        if not (self.email and self.phone):
            missing.append("Email & phone")

        optional = {
            "Certifications": self.certifications,
            "Achievements": self.achievements,
            "Languages": self.languages,
        }
        for label, value in optional.items():
            if not value:
                missing.append(label + " (optional)")

        filled = 10 - len(missing)
        return round(100 * filled / 10), [m.replace(" (optional)", "") for m in missing
                                          if "(optional)" not in m]
