"""Authenticated bounded feature APIs. Original Phase 2 envelopes stay compatible."""
from threading import BoundedSemaphore, Lock
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query, Response
from sqlalchemy import select
from backend.api_v1.errors import APIError
from backend.cloud.auth import current_user, Identity
from backend.cloud.routes import services, owned_ready
from backend.cloud.models import Resume, Analysis, History, SavedResume
from backend.cloud.feature_schemas import (AnalyzeInput, MatchInput, AnalysisRecord, RecordSummary, MatchRecord,
    ImproveInput, Improvements, DraftInput, DraftRecord, DraftSummary, Template)
from backend.cloud import feature_engine as engine

router = APIRouter(prefix='/api/v1', tags=['owned features'], dependencies=[])
User = Annotated[Identity, Depends(current_user)]
capacity = BoundedSemaphore(2)
active = set()
active_lock = Lock()


def feature_slot(user: User):
    with active_lock:
        if user.id in active or not capacity.acquire(blocking=False):
            raise APIError('busy', 'A processing request is already active. Try again shortly.', 429)
        active.add(user.id)
    try:
        yield
    finally:
        with active_lock:
            active.discard(user.id)
            capacity.release()


Slot = Annotated[None, Depends(feature_slot)]


def original(request, user, id):
    db, storage = services(request, user)
    with db.sessions() as session:
        row = owned_ready(db, session, user, id)
        path = row.object_path
        suffix = '.' + row.metadata_json['file_type']
    if not path.startswith(str(user.id) + '/'):
        raise APIError('not_found', 'Resource not found.', 404)
    try:
        data = storage.read(path, min(request.app.state.api_settings.max_upload_bytes, 10 * 1024 * 1024))
    except Exception:
        raise APIError('cloud_unavailable', 'Stored document unavailable. Please try again.', 503) from None
    return db, engine.parse_original(data, suffix)


def save_result(db, user, resume_id, kind, payload, score=None):
    with db.sessions.begin() as session:
        owned_ready(db, session, user, resume_id)  # Recheck after CPU/provider work.
        row = Analysis(user_id=user.id, resume_id=resume_id, kind=kind,
                       summary_json={'ats_score': score, 'report' if kind == 'analysis' else 'result': payload})
        session.add(row)
        session.flush()
        session.add(History(user_id=user.id, event='analysis_created' if kind == 'analysis' else 'job_matched', resource_id=row.id))
        return row


def report_record(row):
    if row.kind != 'analysis' or not row.resume_id or 'report' not in row.summary_json:
        raise APIError('not_found', 'Resource not found.', 404)
    return AnalysisRecord(id=row.id, resume_id=row.resume_id, created_at=row.created_at, report=row.summary_json['report'])


@router.post('/resumes/{id}/analyses', response_model=AnalysisRecord, status_code=201)
def analyze(id: UUID, payload: AnalyzeInput, request: Request, user: User, slot: Slot):
    db, parsed = original(request, user, id)
    report = engine.analyze_resume(parsed, payload.job_description)
    return report_record(save_result(db, user, id, 'analysis', report.model_dump(mode='json'), report.ats.overall))


@router.get('/resumes/{id}/analyses', response_model=list[RecordSummary])
def analyses(id: UUID, request: Request, user: User, offset: Annotated[int, Query(ge=0)] = 0):
    db, _ = services(request, user)
    with db.sessions() as session:
        owned_ready(db, session, user, id)
        rows = session.scalars(select(Analysis).where(Analysis.user_id == user.id, Analysis.resume_id == id, Analysis.kind == 'analysis')
                               .order_by(Analysis.created_at.desc(), Analysis.id).offset(offset).limit(100)).all()
        return [RecordSummary(id=row.id, resume_id=id, created_at=row.created_at, ats_score=row.summary_json.get('ats_score')) for row in rows]


@router.get('/analysis-reports/{id}', response_model=AnalysisRecord)
def report(id: UUID, request: Request, user: User):
    db, _ = services(request, user)
    with db.sessions() as session:
        row = db.owned(session, Analysis, user.id, id)
        return report_record(row)


@router.post('/resumes/{id}/matches', response_model=MatchRecord, status_code=201)
def match(id: UUID, payload: MatchInput, request: Request, user: User, slot: Slot):
    db, parsed = original(request, user, id)
    result = engine.match_resume(parsed, payload.job_description)
    row = save_result(db, user, id, 'match', result.model_dump(mode='json'))
    return MatchRecord(id=row.id, resume_id=id, created_at=row.created_at, result=result)


@router.get('/job-matches/{id}', response_model=MatchRecord)
def get_match(id: UUID, request: Request, user: User):
    db, _ = services(request, user)
    with db.sessions() as session:
        row = db.owned(session, Analysis, user.id, id)
        if row.kind != 'match' or not row.resume_id:
            raise APIError('not_found', 'Resource not found.', 404)
        return MatchRecord(id=row.id, resume_id=row.resume_id, created_at=row.created_at, result=row.summary_json['result'])


@router.post('/resumes/{id}/improvements', response_model=Improvements)
def improve(id: UUID, payload: ImproveInput, request: Request, user: User, slot: Slot):
    _, parsed = original(request, user, id)
    items = engine.improve_resume(parsed, payload, request.app.state.cloud_ai_enabled)
    return Improvements(items=items, provider_used=any(item.source == 'openai' for item in items),
                        notice='Review every edit against your actual experience. No prompts or suggestions are persisted. AI runs only with request consent and server opt-in; unsupported generation falls back to source-preserving rules.')


@router.get('/builder/templates', response_model=list[Template])
def templates(user: User):
    return engine.templates()


def draft_record(row):
    return DraftRecord(id=row.id, created_at=row.created_at, updated_at=row.updated_at, **row.data_json)


@router.post('/builder/drafts', response_model=DraftRecord, status_code=201)
def create_draft(payload: DraftInput, request: Request, user: User):
    db, _ = services(request, user)
    with db.sessions.begin() as session:
        row = SavedResume(user_id=user.id, data_json=payload.model_dump())
        session.add(row)
        session.flush()
        session.add(History(user_id=user.id, event='draft_saved', resource_id=row.id))
        return draft_record(row)


@router.get('/builder/drafts', response_model=list[DraftSummary])
def drafts(request: Request, user: User, offset: Annotated[int, Query(ge=0)] = 0):
    db, _ = services(request, user)
    return [DraftSummary(id=row.id, template=row.data_json.get('template', 'essential'), created_at=row.created_at, updated_at=row.updated_at)
            for row in db.list(SavedResume, user.id, offset)]


@router.get('/builder/drafts/{id}', response_model=DraftRecord)
def get_draft(id: UUID, request: Request, user: User):
    db, _ = services(request, user)
    with db.sessions() as session:
        return draft_record(db.owned(session, SavedResume, user.id, id))


@router.put('/builder/drafts/{id}', response_model=DraftRecord)
def update_draft(id: UUID, payload: DraftInput, request: Request, user: User):
    db, _ = services(request, user)
    return draft_record(db.update(SavedResume, user.id, id, data_json=payload.model_dump()))


@router.delete('/builder/drafts/{id}', status_code=204)
def delete_draft(id: UUID, request: Request, user: User):
    db, _ = services(request, user)
    with db.sessions.begin() as session:
        session.delete(db.owned(session, SavedResume, user.id, id))
        session.add(History(user_id=user.id, event='draft_deleted', resource_id=id))


@router.post('/builder/drafts/{id}/exports/{fmt}')
def export(id: UUID, fmt: Literal['pdf','docx'], request: Request, user: User, slot: Slot):
    db, _ = services(request, user)
    with db.sessions() as session:
        payload = DraftInput.model_validate(db.owned(session, SavedResume, user.id, id).data_json)
    content = engine.export_draft(payload, fmt)
    with db.sessions.begin() as session:
        db.owned(session, SavedResume, user.id, id)  # No success after concurrent deletion.
        session.add(History(user_id=user.id, event='export_generated', resource_id=id))
    mime = 'application/pdf' if fmt == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(content, media_type=mime, headers={'Content-Disposition': f'attachment; filename="resume.{fmt}"',
                    'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})
