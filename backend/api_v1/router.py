from fastapi import APIRouter

from backend.api_v1.routes import health, resumes

router = APIRouter()
router.include_router(health.router)
router.include_router(resumes.router, prefix="/api/resume", tags=["resumes"])
