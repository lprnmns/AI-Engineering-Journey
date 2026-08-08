"""HTTP error envelope and exception mappings."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..domain.errors import ErrorCode, ServiceError
from ..observability.request_id import get_request_id


class ErrorDetail(BaseModel):
    """Safe, stable error details exposed to API consumers."""

    code: ErrorCode
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    """Top-level error response contract."""

    error: ErrorDetail


_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCode.UPLOAD_TOO_LARGE: status.HTTP_413_CONTENT_TOO_LARGE,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    ErrorCode.DOCUMENT_PARSE_FAILED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.DOCUMENT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.INGESTION_CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.DOCUMENT_BUSY: status.HTTP_409_CONFLICT,
    ErrorCode.DEPENDENCY_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _error_response(*, code: ErrorCode, message: str, request_id: str) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(
        status_code=_STATUS_BY_CODE[code],
        content=payload.model_dump(mode="json"),
        headers={"X-Request-ID": request_id},
    )


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map an expected application error to its public HTTP contract."""

    del request
    if not isinstance(exc, ServiceError):
        raise TypeError("service_error_handler received an unexpected exception")
    return _error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(),
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide internal validation details behind a stable public error."""

    del request
    if not isinstance(exc, RequestValidationError):
        raise TypeError("validation_error_handler received an unexpected exception")
    return _error_response(
        code=ErrorCode.INVALID_REQUEST,
        message="Request validation failed",
        request_id=get_request_id(),
    )


def openapi_error_responses() -> dict[int, dict[str, Any]]:
    """Return reusable OpenAPI response metadata for future routes."""

    return {
        status.HTTP_400_BAD_REQUEST: {"model": ErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ErrorEnvelope},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorEnvelope},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorEnvelope},
    }
