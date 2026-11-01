"""
Database access layer.

A single module owns engine creation and session management so every other
part of the app goes through the same, safe (parameterised via the ORM) access
path. Ships with SQLite; DATABASE_URL makes switching engines trivial.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import config
from database.models import AnalysisRecord, Base, SavedResume

logger = config.get_logger("database")


class Database:
    """Thin, explicit wrapper around SQLAlchemy sessions.

    Example:
        db = Database()
        db.save_analysis({...})
        for record in db.list_analyses(): ...
    """

    def __init__(self, url: str | None = None, echo: bool = False):
        self.url = url or f"sqlite:///{config.DATA_DIR / 'resumeiq.db'}"
        self.engine = create_engine(self.url, echo=echo, future=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.create_all()

    # -- lifecycle ---------------------------------------------------------

    def create_all(self) -> None:
        """Create tables that do not exist yet (safe to call repeatedly)."""
        Base.metadata.create_all(self.engine)
        logger.info("Database ready at %s", self.url)

    def session(self) -> Session:
        """Provide a short-lived session (caller closes it or uses a block)."""
        return self._session_factory()

    # -- analyses ----------------------------------------------------------

    def save_analysis(self, payload: dict[str, Any]) -> AnalysisRecord:
        """Insert one analysis record from a flat dict payload."""
        record = AnalysisRecord(
            file_name=payload.get("file_name", "resume"),
            file_type=payload.get("file_type", "pdf"),
            ats_score=float(payload.get("ats_score", 0.0)),
            readability_score=float(payload.get("readability_score", 0.0)),
            structure_score=float(payload.get("structure_score", 0.0)),
            completeness_score=float(payload.get("completeness_score", 0.0)),
            keywords_score=float(payload.get("keywords_score", 0.0)),
            formatting_score=float(payload.get("formatting_score", 0.0)),
            contact_score=float(payload.get("contact_score", 0.0)),
            word_count=int(payload.get("word_count", 0)),
            job_match_score=payload.get("job_match_score"),
            report_json=payload.get("report_json", {}),
            resume_text=(payload.get("resume_text") or "")[:200_000],
        )
        with self.session() as s:
            s.add(record)
            s.commit()
            logger.info("Saved analysis #%s (%s, score %.0f)", record.id, record.file_name, record.ats_score)
            return record

    def get_analysis(self, record_id: int) -> AnalysisRecord | None:
        with self.session() as s:
            return s.get(AnalysisRecord, record_id)

    def list_analyses(self, limit: int = 100, offset: int = 0) -> Sequence[AnalysisRecord]:
        """Newest first; loaded detached (expire_on_commit=False) so safe to read."""
        with self.session() as s:
            stmt = (
                select(AnalysisRecord)
                .order_by(AnalysisRecord.uploaded_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return s.scalars(stmt).all()

    def delete_analysis(self, record_id: int) -> bool:
        with self.session() as s:
            record = s.get(AnalysisRecord, record_id)
            if not record:
                return False
            s.delete(record)
            s.commit()
            logger.info("Deleted analysis #%s", record_id)
            return True

    def score_trend(self, limit: int = 20) -> list[tuple[str, float]]:
        """Return [(date_iso, score)] oldest→newest for the trend chart."""
        with self.session() as s:
            stmt = (
                select(AnalysisRecord.uploaded_at, AnalysisRecord.ats_score)
                .order_by(AnalysisRecord.uploaded_at.asc())
                .limit(limit)
            )
            rows = s.execute(stmt).all()
        return [(r[0].isoformat()[:10], r[1]) for r in rows if r[0]]

    # -- saved resumes ------------------------------------------------------

    def save_resume(self, name: str, template_id: str, data: dict, role_type: str = "Experienced",
                    resume_id: int | None = None) -> SavedResume:
        """Create a resume row, or update an existing one when resume_id given."""
        with self.session() as s:
            record = s.get(SavedResume, resume_id) if resume_id else None
            if record is None:
                record = SavedResume(name=name, template_id=template_id, data_json=data, role_type=role_type)
                s.add(record)
            else:
                record.name, record.template_id, record.data_json, record.role_type = (
                    name, template_id, data, role_type)
            s.commit()
            return record

    def list_resumes(self) -> Sequence[SavedResume]:
        with self.session() as s:
            stmt = select(SavedResume).order_by(SavedResume.updated_at.desc())
            return s.scalars(stmt).all()

    def get_resume(self, resume_id: int) -> SavedResume | None:
        with self.session() as s:
            return s.get(SavedResume, resume_id)

    def delete_resume(self, resume_id: int) -> bool:
        with self.session() as s:
            record = s.get(SavedResume, resume_id)
            if not record:
                return False
            s.delete(record)
            s.commit()
            return True

    # -- generic stats -------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self.session() as s:
            n_analyses = s.scalar(select(func.count()).select_from(AnalysisRecord)) or 0
            avg_score = s.scalar(select(func.avg(AnalysisRecord.ats_score))) or 0.0
            best_score = s.scalar(select(func.max(AnalysisRecord.ats_score))) or 0.0
            n_resumes = s.scalar(select(func.count()).select_from(SavedResume)) or 0
        return {
            "analyses": int(n_analyses),
            "avg_score": round(float(avg_score), 1),
            "best_score": round(float(best_score), 1),
            "resumes": int(n_resumes),
        }


def record_to_dict(record: AnalysisRecord) -> dict:
    """Serialise an analysis record (including nested JSON) for UI/exports."""
    return {
        "id": record.id,
        "file_name": record.file_name,
        "file_type": record.file_type,
        "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else "",
        "ats_score": record.ats_score,
        "scores": {
            "readability": record.readability_score,
            "structure": record.structure_score,
            "completeness": record.completeness_score,
            "keywords": record.keywords_score,
            "formatting": record.formatting_score,
            "contact": record.contact_score,
        },
        "word_count": record.word_count,
        "job_match_score": record.job_match_score,
        "report": record.report_json or {},
    }


# Single shared instance for the whole app (SQLite: one engine is fine).
_shared: Database | None = None


def get_db() -> Database:
    """Lazily create (and reuse) the shared Database instance."""
    global _shared
    if _shared is None:
        _shared = Database()
    return _shared
