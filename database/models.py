"""
Database models (SQLAlchemy ORM).

Two tables power ResumeIQ:

1. AnalysisRecord — one row per uploaded-resume analysis. The full report is
   stored as JSON so historical reports can be reopened without re-parsing.
2. SavedResume   — one row per resume built in the Resume Builder. The form
   data is stored as JSON; rendering to PDF/DOCX happens on demand.

Contact details are stored only because the user typed them into the builder —
no third-party services receive resume text.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Common declarative base for every ResumeIQ table."""


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp (SQLite-friendly, ISO sortable)."""
    return datetime.now(timezone.utc)


class AnalysisRecord(Base):
    """A completed ATS analysis of an uploaded resume."""

    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255))            # display name only
    file_type: Mapped[str] = mapped_column(String(10))             # pdf / docx
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Core numbers kept as columns so the dashboard/history can query them.
    ats_score: Mapped[float] = mapped_column(Float)
    readability_score: Mapped[float] = mapped_column(Float, default=0.0)
    structure_score: Mapped[float] = mapped_column(Float, default=0.0)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    keywords_score: Mapped[float] = mapped_column(Float, default=0.0)
    formatting_score: Mapped[float] = mapped_column(Float, default=0.0)
    contact_score: Mapped[float] = mapped_column(Float, default=0.0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    job_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full report payload: strengths, weaknesses, recommendations, issues, ...
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Extracted resume text, optionally stored so history can be reopened.
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavedResume(Base):
    """A resume created/edited in the Resume Builder."""

    __tablename__ = "saved_resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))                 # resume title
    template_id: Mapped[str] = mapped_column(String(50))
    role_type: Mapped[str] = mapped_column(String(30), default="Experienced")

    data_json: Mapped[dict] = mapped_column(JSON, default=dict)    # full form data
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class KeywordHistory(Base):
    """Job-description keywords the user matched against (simple history log)."""

    __tablename__ = "keyword_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_title: Mapped[str] = mapped_column(String(200), default="")
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    missing_skills_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
