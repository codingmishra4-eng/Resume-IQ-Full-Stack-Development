from fastapi import APIRouter, Request
from backend.api_v1.errors import error_response

from backend.api_v1.schemas.common import HealthResponse, HomeResponse

router = APIRouter(tags=["health"])


@router.get("/", response_model=HomeResponse)
def home() -> HomeResponse:
    return HomeResponse(message="Welcome to ResumeIQ API")


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    # Liveness only; no database, storage, or authentication readiness claim.
    return HealthResponse(status="ok", application="ResumeIQ")


@router.get('/api/ready', include_in_schema=False)
def ready(request: Request):
    db = request.app.state.cloud_db
    if db is None:
        return error_response(503, 'not_ready', 'Cloud service is not ready.')
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            flags = conn.execute(text("SELECT current_user, rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication FROM pg_roles WHERE rolname=current_user")).one()
            if flags != ('resumeiq_runtime',False):
                raise RuntimeError()
            required = conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='cloud_analyses' AND column_name IN ('resume_id','kind')"))
            if required != 2:
                raise RuntimeError()
        return {'status':'ready'}
    except Exception:
        return error_response(503, 'not_ready', 'Cloud service is not ready.')
