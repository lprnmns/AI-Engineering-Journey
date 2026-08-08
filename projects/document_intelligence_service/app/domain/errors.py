"""Framework-independent application error vocabulary."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable error codes exposed by the service contract."""

    INVALID_REQUEST = "INVALID_REQUEST"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    DOCUMENT_PARSE_FAILED = "DOCUMENT_PARSE_FAILED"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    INGESTION_CONFLICT = "INGESTION_CONFLICT"
    DOCUMENT_BUSY = "DOCUMENT_BUSY"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


class ServiceError(Exception):
    """Expected application error that the API can safely expose."""

    def __init__(self, *, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
