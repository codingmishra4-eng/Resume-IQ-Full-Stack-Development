from typing import Literal

from fastapi import UploadFile
from pydantic import Field

from backend.api_v1.schemas.common import APIModel


class ResumeUploadRequest(APIModel):
    """Multipart file supplied through the typed FastAPI File dependency."""

    file: UploadFile


class ResumeMetadata(APIModel):
    # A generated display name prevents leaking names/paths in client filenames.
    file_name: Literal["resume.pdf", "resume.docx"]
    file_type: Literal["pdf", "docx"]
    pages: int = Field(ge=0)
    word_count: int = Field(ge=0)
    section_order: list[str]
    bullet_count: int = Field(ge=0)
    tables_detected: int = Field(ge=0)
    images_detected: int = Field(ge=0)
    headings_look_caps: bool


class ResumeUploadResponse(APIModel):
    success: Literal[True] = True
    resume: ResumeMetadata
