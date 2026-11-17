"""Cloud-only tables; no local table changes or implicit production DDL."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, CheckConstraint, JSON, String, Uuid, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Owned:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)


class Resume(Owned, Base):
    __tablename__ = 'cloud_resumes'
    __table_args__ = (CheckConstraint("state IN ('pending','ready','deleting')", name='resume_state'), UniqueConstraint('id', 'user_id', name='uq_cloud_resume_owner'))
    object_path: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(16), default='pending', nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class Analysis(Owned, Base):
    __tablename__ = 'cloud_analyses'
    __table_args__ = (
        ForeignKeyConstraint(['resume_id', 'user_id'], ['cloud_resumes.id', 'cloud_resumes.user_id'], ondelete='CASCADE', name='fk_cloud_analysis_resume_owner'),
        CheckConstraint("kind IN ('analysis','match')", name='cloud_analysis_kind'),
    )
    resume_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default='analysis', nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SavedResume(Owned, Base):
    __tablename__ = 'cloud_saved_resumes'
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class History(Owned, Base):
    __tablename__ = 'cloud_history'
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
