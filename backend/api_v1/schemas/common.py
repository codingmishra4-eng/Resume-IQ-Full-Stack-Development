from typing import Literal

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomeResponse(APIModel):
    message: str


class HealthResponse(APIModel):
    status: Literal["ok"]
    application: Literal["ResumeIQ"]


class ErrorResponse(APIModel):
    detail: str
    code: str
