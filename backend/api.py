"""Compatibility entry point: uvicorn backend.api:app."""

from fastapi import FastAPI
from backend.cloud.settings import CloudSettings
from backend.cloud.auth import TokenVerifier
from backend.cloud.database import CloudDatabase
from backend.cloud.storage import PrivateStorage
from backend.cloud.routes import router as cloud_router, me, Profile
from starlette.middleware.cors import CORSMiddleware

from backend.api_v1.errors import register_error_handlers
from backend.api_v1.middleware import UploadBodyLimitMiddleware
from backend.api_v1.router import router
from backend.api_v1.settings import APISettings


def create_app(settings: APISettings | None = None) -> FastAPI:
    settings = settings or APISettings.from_env()
    application = FastAPI(
        title="ResumeIQ API",
        description="ResumeIQ local tools and optional authenticated cloud API",
        version="2.0.0",
    )
    application.state.api_settings = settings
    cloud = CloudSettings.from_env()
    application.state.token_verifier = TokenVerifier(cloud) if cloud else None
    application.state.cloud_db = CloudDatabase(cloud.database_url) if cloud else None
    application.state.private_storage = PrivateStorage(cloud) if cloud else None
    register_error_handlers(application)
    application.include_router(cloud_router)
    application.add_api_route('/api/me', me, response_model=Profile, methods=['GET'])
    application.include_router(router)
    application.add_middleware(
        UploadBodyLimitMiddleware, max_bytes=settings.max_upload_bytes + 64 * 1024,
    )
    # CORS wraps the body guard, including its early rejection responses.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
    return application


app = create_app()
