from fastapi import APIRouter

from backend.api_v1.schemas.common import HealthResponse, HomeResponse

router = APIRouter(tags=["health"])


@router.get("/", response_model=HomeResponse)
def home() -> HomeResponse:
    return HomeResponse(message="Welcome to ResumeIQ API")


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    # Liveness only; no database, storage, or authentication readiness claim.
    return HealthResponse(status="ok", application="ResumeIQ")
