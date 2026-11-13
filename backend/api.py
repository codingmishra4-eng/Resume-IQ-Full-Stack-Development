"""Compatibility entry point: uvicorn backend.api:app."""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from backend.api_v1.errors import register_error_handlers
from backend.api_v1.middleware import UploadBodyLimitMiddleware
from backend.api_v1.router import router
from backend.api_v1.settings import APISettings


def create_app(settings: APISettings | None = None) -> FastAPI:
    settings = settings or APISettings.from_env()
    application = FastAPI(
        title="ResumeIQ API",
        description="Backend API for ResumeIQ (Phase 1; authentication not implemented)",
        version="1.0.0",
    )
    application.state.api_settings = settings
    register_error_handlers(application)
    application.include_router(router)
    application.add_middleware(
        UploadBodyLimitMiddleware, max_bytes=settings.max_upload_bytes + 64 * 1024,
    )
    # CORS wraps the body guard, including its early rejection responses.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    return application


app = create_app()
