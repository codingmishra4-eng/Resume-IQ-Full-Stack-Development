from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from starlette.concurrency import run_in_threadpool

import config
from backend.api_v1.errors import APIError
from backend.api_v1.schemas.common import ErrorResponse
from backend.api_v1.schemas.resumes import ResumeMetadata, ResumeUploadRequest, ResumeUploadResponse
from backend.api_v1.upload_validation import validate_content
from backend.resume_parser import ParseError, ResumeParser, SECTION_ALIASES

router = APIRouter()


async def upload_request(
    request: Request,
    file: Annotated[UploadFile, File(
        description="One PDF or DOCX resume; content is validated server-side.",
        json_schema_extra={"format": "binary"},
    )],
) -> ResumeUploadRequest:
    form = await request.form()
    if len(form.multi_items()) != 1:
        raise APIError("invalid_request", "Supply exactly one file field and no additional form fields.")
    return ResumeUploadRequest(file=file)


def parse_metadata(data: bytes, suffix: str) -> ResumeMetadata:
    validate_content(data, suffix)
    try:
        # Use a generated name; the original name may contain personal data.
        parsed = ResumeParser().parse(data, f"resume{suffix}")
    except (ParseError, ValueError, RuntimeError) as exc:
        raise APIError("invalid_file", "The document could not be read. Upload a valid text-based PDF or DOCX resume.") from exc
    # Explicit allowlist: never serialize ParsedResume or arbitrary diagnostics.
    return ResumeMetadata(
        file_name=f"resume{suffix}", file_type=parsed.file_type,
        pages=parsed.pages, word_count=parsed.word_count,
        section_order=[name for name in parsed.section_order if name in SECTION_ALIASES],
        bullet_count=parsed.bullet_count, tables_detected=parsed.tables_detected,
        images_detected=parsed.images_detected, headings_look_caps=parsed.headings_look_caps,
    )


@router.post(
    "/upload", response_model=ResumeUploadResponse,
    responses={code: {"model": ErrorResponse} for code in (400, 422, 500)},
)
async def upload_resume(
    request: Request,
    upload: Annotated[ResumeUploadRequest, Depends(upload_request)],
) -> ResumeUploadResponse:
    file = upload.file
    try:
        # Filename and browser MIME type are untrusted. Only the suffix is used;
        # binary signature/container checks and the real parser validate content.
        name = file.filename or ""
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if suffix not in config.ALLOWED_EXTENSIONS:
            raise APIError("unsupported_format", "Please upload a PDF or DOCX resume.")
        limit = min(request.app.state.api_settings.max_upload_bytes, int(ResumeParser.MAX_BYTES))
        data = await file.read(limit + 1)
        if not data:
            raise APIError("empty_file", "The uploaded file is empty.")
        if len(data) > limit:
            raise APIError("file_too_large", "Upload exceeds the configured size limit.")
        # PDF/Word processing must not run directly on the async event loop.
        metadata = await run_in_threadpool(parse_metadata, data, suffix)
        return ResumeUploadResponse(resume=metadata)
    finally:
        await file.close()
