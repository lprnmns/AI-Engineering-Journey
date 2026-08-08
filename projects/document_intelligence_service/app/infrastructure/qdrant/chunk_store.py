"""Qdrant persistence adapter for page-aware child chunks."""

from collections.abc import Sequence
import uuid

from qdrant_client import QdrantClient, models

from ...domain.chunks import ChildChunk
from ...domain.ingestion import VersionVerification
from ...domain.vectors import SparseVector
from .schema import QdrantSchema, QdrantSchemaManager


# Backwards-compatible name used by the first Qdrant schema tests.
SparseEmbedding = SparseVector


class QdrantChunkStore:
    """Persist dense+sparse child chunk vectors with source payload."""

    def __init__(self, client: QdrantClient, schema: QdrantSchema) -> None:
        self._client = client
        self._schema_manager = QdrantSchemaManager(client, schema)

    @property
    def collection_name(self) -> str:
        """Return the configured collection name."""

        return self._schema_manager.schema.collection_name

    @property
    def client(self) -> QdrantClient:
        """Expose the client for diagnostics and integration tests."""

        return self._client

    def ensure_schema(self) -> None:
        """Create or validate the collection before use."""

        self._schema_manager.ensure_collection()

    def stage_version(
        self,
        *,
        chunks: Sequence[ChildChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
        pipeline_fingerprint: str,
        language: str = "unknown",
    ) -> None:
        """Write all version points as inactive/staged data."""

        self.upsert(
            chunks=chunks,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
            pipeline_fingerprint=pipeline_fingerprint,
            language=language,
            is_active=False,
        )

    def verify_version(
        self,
        *,
        document_id: str,
        version_id: str,
        expected_chunk_count: int,
    ) -> VersionVerification:
        """Validate the staged point count and required source metadata."""

        if expected_chunk_count <= 0:
            raise ValueError("expected_chunk_count must be greater than zero")
        self.ensure_schema()
        version_filter = self._version_filter(document_id, version_id)
        inactive_filter = models.Filter(
            must=[
                *(version_filter.must or []),
                models.FieldCondition(
                    key="is_active",
                    match=models.MatchValue(value=False),
                ),
            ]
        )
        actual_count = self._client.count(
            collection_name=self.collection_name,
            count_filter=version_filter,
            exact=True,
        ).count
        inactive_count = self._client.count(
            collection_name=self.collection_name,
            count_filter=inactive_filter,
            exact=True,
        ).count
        records, _ = self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=version_filter,
            limit=max(expected_chunk_count, 1),
            with_payload=True,
            with_vectors=False,
        )
        required_payload = {
            "chunk_id",
            "parent_id",
            "document_id",
            "version_id",
            "source",
            "text",
            "page_start",
            "page_end",
            "text_hash",
            "pipeline_fingerprint",
            "is_active",
        }
        metadata_complete = len(records) == actual_count and all(
            record.payload is not None
            and required_payload.issubset(record.payload.keys())
            for record in records
        )
        return VersionVerification(
            document_id=document_id,
            version_id=version_id,
            expected_chunk_count=expected_chunk_count,
            actual_chunk_count=actual_count,
            inactive_chunk_count=inactive_count,
            schema_valid=True,
            metadata_complete=metadata_complete,
        )

    def activate_version(
        self,
        *,
        document_id: str,
        version_id: str,
        verification: VersionVerification,
    ) -> None:
        """Expose a verified version and hide previous versions for the document."""

        if not verification.is_valid:
            raise ValueError("cannot activate an unverified Qdrant version")
        self.ensure_schema()
        document_filter = self._document_filter(document_id)
        version_filter = self._version_filter(document_id, version_id)
        self._client.set_payload(
            collection_name=self.collection_name,
            payload={"is_active": False},
            points=document_filter,
            wait=True,
        )
        self._client.set_payload(
            collection_name=self.collection_name,
            payload={"is_active": True},
            points=version_filter,
            wait=True,
        )

    def upsert(
        self,
        *,
        chunks: Sequence[ChildChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
        pipeline_fingerprint: str,
        language: str = "unknown",
        is_active: bool = False,
    ) -> None:
        """Validate vector alignment and upsert deterministic points."""

        if not (len(chunks) == len(dense_vectors) == len(sparse_vectors)):
            raise ValueError("chunks and vector batches must have equal lengths")
        if not chunks:
            return

        self.ensure_schema()
        points: list[models.PointStruct] = []
        for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True):
            if len(dense) != self._schema_manager.schema.dense_size:
                raise ValueError(
                    f"chunk {chunk.chunk_id} has dense dimension {len(dense)}, "
                    f"expected {self._schema_manager.schema.dense_size}"
                )
            if len(sparse.indices) != len(sparse.values):
                raise ValueError("sparse indices and values must have equal lengths")
            if any(index < 0 for index in sparse.indices):
                raise ValueError("sparse indices must be non-negative")
            points.append(
                models.PointStruct(
                    id=self.point_id(chunk.version_id, chunk.chunk_id),
                    vector={
                        self._schema_manager.schema.dense_name: list(dense),
                        self._schema_manager.schema.sparse_name: models.SparseVector(
                            indices=list(sparse.indices),
                            values=list(sparse.values),
                        ),
                    },
                    payload=self.payload(
                        chunk,
                        pipeline_fingerprint=pipeline_fingerprint,
                        language=language,
                        is_active=is_active,
                    ),
                )
            )
        self._client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    @staticmethod
    def point_id(version_id: str, chunk_id: str) -> str:
        """Return a stable UUID for one versioned child chunk."""

        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"document-intelligence/{version_id}/{chunk_id}",
            )
        )

    @staticmethod
    def payload(
        chunk: ChildChunk,
        *,
        pipeline_fingerprint: str,
        language: str,
        is_active: bool,
    ) -> dict[str, str | int | bool]:
        """Map source metadata to an indexed Qdrant payload."""

        return {
            "chunk_id": chunk.chunk_id,
            "parent_id": chunk.parent_id,
            "document_id": chunk.document_id,
            "version_id": chunk.version_id,
            "source": chunk.source,
            "title": chunk.title,
            "text": chunk.text,
            "chunk_index": chunk.chunk_index,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "token_count": chunk.token_count_estimate,
            "text_hash": chunk.text_hash,
            "pipeline_fingerprint": pipeline_fingerprint,
            "language": language,
            "is_active": is_active,
        }

    @staticmethod
    def _document_filter(document_id: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        )

    @staticmethod
    def _version_filter(document_id: str, version_id: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                ),
                models.FieldCondition(
                    key="version_id",
                    match=models.MatchValue(value=version_id),
                ),
            ]
        )
