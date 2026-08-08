"""Document resource contract routes."""

from typing import Annotated

from fastapi import APIRouter, File, Header, Path, Query, UploadFile, status

from ..errors import openapi_error_responses
from ._not_ready import feature_not_ready
from .contracts import (
    DeleteDocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_202_ACCEPTED: {"model": DocumentUploadResponse},
        status.HTTP_501_NOT_IMPLEMENTED: {"description": "Scaffold only"},
        **openapi_error_responses(),
    },
)
async def create_document(
    file: Annotated[UploadFile, File(description="PDF document")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DocumentUploadResponse:
    """Accept a PDF for asynchronous ingestion (implementation follows on Day 2)."""

    del file, idempotency_key
    feature_not_ready("Document ingestion")


@router.get(
    "",
    response_model=DocumentListResponse,
    responses={**openapi_error_responses()},
)
async def list_documents(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> DocumentListResponse:
    """List documents with bounded cursor pagination."""

    del limit, cursor
    feature_not_ready("Document listing")


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses={**openapi_error_responses()},
)
async def get_document(
    document_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> DocumentDetailResponse:
    """Return one document and its available versions."""

    del document_id
    feature_not_ready("Document detail")


@router.delete(
    "/{document_id}",
    response_model=DeleteDocumentResponse,
    responses={**openapi_error_responses()},
)
async def delete_document(
    document_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> DeleteDocumentResponse:
    """Delete a document unless an active ingestion job makes it busy."""

    del document_id
    feature_not_ready("Document deletion")
