"""Stable public errors. Never serialize exception bodies or request input."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from backend.api_v1.schemas.common import ErrorResponse


class APIError(HTTPException):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def error_response(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail, code=code).model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc, APIError):
            response = error_response(exc.status_code, exc.code, exc.detail)
            if exc.headers:
                response.headers.update(exc.headers)
            return response
        # Multipart parser exceptions can contain attacker-controlled input.
        messages = {400: "Malformed request.", 404: "Not found.", 405: "Method not allowed."}
        response = error_response(exc.status_code, "http_error", messages.get(exc.status_code, "Request failed."))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "invalid_request", "A resume file is required in the multipart file field.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Do not log exception messages, tracebacks, filenames, or resume contents.
        response = error_response(500, "internal_error", "The request could not be completed. Please try again.")
        # ServerErrorMiddleware sits outside user middleware. Apply the same
        # exact origin policy to its fallback so browser clients can read it.
        origin = request.headers.get("origin")
        if origin in request.app.state.api_settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response
