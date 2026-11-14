"""Versioned authenticated cloud contracts; legacy upload stays unchanged."""
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, Query, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
import config
from backend.api_v1.errors import APIError
from backend.api_v1.routes.resumes import upload_request, parse_metadata
from backend.api_v1.schemas.resumes import ResumeUploadRequest, ResumeMetadata
from backend.resume_parser import ResumeParser
from backend.cloud.auth import Identity, current_user
from backend.cloud.models import Resume, Analysis, History

router = APIRouter(prefix='/api/v1', tags=['private cloud'])
User = Annotated[Identity, Depends(current_user)]


class Profile(BaseModel):
    id: UUID


class StoredResume(BaseModel):
    id: UUID
    created_at: datetime
    metadata: ResumeMetadata


class AnalysisSummary(BaseModel):
    id: UUID
    created_at: datetime
    # Explicit allowlist: no raw text, names, contact details or arbitrary JSON.
    ats_score: float | None = None


class Download(BaseModel):
    url: str
    expires_in: int = 60


def services(request):
    db, storage = request.app.state.cloud_db, request.app.state.private_storage
    if db is None or storage is None:
        raise APIError('cloud_unavailable', 'Cloud service unavailable.', 503)
    return db, storage


def public(row):
    return StoredResume(id=row.id, created_at=row.created_at, metadata=row.metadata_json)


def owned_ready(db, session, user, id):
    row = db.owned(session, Resume, user.id, id)
    if row.state != 'ready':
        raise APIError('not_found', 'Resource not found.', 404)
    return row


@router.get('/me', response_model=Profile)
def me(user: User):
    return Profile(id=user.id)


@router.post('/resumes', response_model=StoredResume, status_code=201)
async def upload(request: Request, user: User,
                 upload: Annotated[ResumeUploadRequest, Depends(upload_request)]):
    file = upload.file
    try:
        name = file.filename or ''
        suffix = '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if suffix not in config.ALLOWED_EXTENSIONS:
            raise APIError('unsupported_format', 'Please upload a PDF or DOCX resume.')
        limit = min(request.app.state.api_settings.max_upload_bytes, int(ResumeParser.MAX_BYTES))
        data = await file.read(limit + 1)
        if not data:
            raise APIError('empty_file', 'The uploaded file is empty.')
        if len(data) > limit:
            raise APIError('file_too_large', 'Upload exceeds the configured size limit.')
        metadata = await run_in_threadpool(parse_metadata, data, suffix)
        return await run_in_threadpool(persist_upload, request, user, data, suffix, metadata)
    finally:
        await file.close()


def persist_upload(request, user, data, suffix, metadata):
    db, storage = services(request)
    # Commit intent FIRST: even uncertain network/commit outcomes remain discoverable.
    row = db.create(Resume, user.id, object_path=f'{user.id}/{uuid4()}{suffix}',
                    state='pending', metadata_json=metadata.model_dump())
    try:
        storage.upload(row.object_path, data, config.ALLOWED_EXTENSIONS[suffix])
        with db.sessions.begin() as session:
            saved = db.owned(session, Resume, user.id, row.id)
            saved.state = 'ready'
            session.add(History(user_id=user.id, event='resume_uploaded', resource_id=row.id))
        return public(row)
    except Exception:
        # Keep pending intent if cleanup fails; operations can retry safely.
        try:
            storage.delete(row.object_path)
            with db.sessions.begin() as session:
                session.delete(db.owned(session, Resume, user.id, row.id))
        except Exception:
            pass
        raise APIError('cloud_unavailable', 'Cloud service unavailable.', 503) from None


@router.get('/resumes', response_model=list[StoredResume])
def list_resumes(request: Request, user: User, offset: Annotated[int, Query(ge=0)] = 0):
    db, _ = services(request)
    return [public(row) for row in db.list(Resume, user.id, offset)]


@router.get('/resumes/{id}', response_model=StoredResume)
def get_resume(id: UUID, request: Request, user: User):
    db, _ = services(request)
    with db.sessions() as session:
        return public(owned_ready(db, session, user, id))


@router.post('/resumes/{id}/download', response_model=Download)
def download(id: UUID, request: Request, response: Response, user: User):
    response.headers["Cache-Control"] = "no-store"
    db, storage = services(request)
    with db.sessions() as session:
        row = owned_ready(db, session, user, id)
        return Download(url=storage.sign(row.object_path))


@router.delete('/resumes/{id}', status_code=204)
def delete_resume(id: UUID, request: Request, user: User):
    db, storage = services(request)
    with db.sessions.begin() as session:
        row = db.owned(session, Resume, user.id, id)
        row.state = 'deleting'
        path = row.object_path
    try:
        storage.delete(path)
        with db.sessions.begin() as session:
            session.delete(db.owned(session, Resume, user.id, id))
            session.add(History(user_id=user.id, event='resume_deleted', resource_id=id))
    except APIError:
        raise
    except Exception:
        raise APIError('cloud_unavailable', 'Cloud service unavailable.', 503) from None


def analysis_public(row):
    return AnalysisSummary(id=row.id, created_at=row.created_at,
                           ats_score=row.summary_json.get('ats_score'))


@router.get('/analyses', response_model=list[AnalysisSummary])
def analyses(request: Request, user: User, offset: Annotated[int, Query(ge=0)] = 0):
    db, _ = services(request)
    return [analysis_public(row) for row in db.list(Analysis, user.id, offset)]


@router.get('/analyses/{id}', response_model=AnalysisSummary)
def analysis(id: UUID, request: Request, user: User):
    db, _ = services(request)
    with db.sessions() as session:
        return analysis_public(db.owned(session, Analysis, user.id, id))


class HistoryEntry(BaseModel):
    id: UUID
    created_at: datetime
    event: str
    resource_id: UUID


@router.get('/history', response_model=list[HistoryEntry])
def history(request: Request, user: User, offset: Annotated[int, Query(ge=0)] = 0):
    db, _ = services(request)
    return [HistoryEntry(id=row.id, created_at=row.created_at, event=row.event,
                         resource_id=row.resource_id) for row in db.list(History, user.id, offset)]
