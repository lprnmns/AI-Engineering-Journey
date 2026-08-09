"""Document catalog use cases shared by HTTP and future worker adapters."""

import asyncio

from ..domain.errors import ErrorCode, ServiceError
from ..domain.ingestion import DocumentPage, DocumentSnapshot
from .ports import ChunkVectorStore, IngestionRegistry


class DocumentService:
    """Coordinate document metadata lifecycle with optional vector cleanup."""

    def __init__(
        self,
        *,
        registry: IngestionRegistry,
        vector_store: ChunkVectorStore | None = None,
    ) -> None:
        self._registry = registry
        self._vector_store = vector_store

    async def list_documents(self, limit: int, cursor: str | None) -> DocumentPage:
        """Return a bounded page of logical document metadata."""

        return await self._registry.list_documents(limit, cursor)

    async def get_document(self, document_id: str) -> DocumentSnapshot:
        """Return a document or a stable not-found error."""

        document = await self._registry.get_document(document_id)
        if document is None:
            raise ServiceError(
                code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="Document was not found",
            )
        return document

    async def delete_document(self, document_id: str) -> None:
        """Remove vector points and mark metadata deleted after busy checks."""

        document = await self.get_document(document_id)
        if document.status.value == "indexing":
            raise ServiceError(
                code=ErrorCode.DOCUMENT_BUSY,
                message="Document has an ingestion job in progress",
            )
        if self._vector_store is not None:
            try:
                await asyncio.to_thread(
                    self._vector_store.delete_document,
                    document.document_id,
                )
            except Exception as error:
                raise ServiceError(
                    code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="Vector store is unavailable for document deletion",
                ) from error
        await self._registry.delete_document(document.document_id)
