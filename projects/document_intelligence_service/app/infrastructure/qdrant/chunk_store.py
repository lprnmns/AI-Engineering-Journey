"""Qdrant persistence adapter for page-aware child chunks."""

from dataclasses import dataclass
from collections.abc import Sequence
import uuid

from qdrant_client import QdrantClient, models

from ...domain.chunks import ChildChunk
from .schema import QdrantSchema, QdrantSchemaManager


@dataclass(frozen=True, slots=True)
class SparseEmbedding:
    """Framework-independent sparse vector values before Qdrant mapping."""

    indices: tuple[int, ...]
    values: tuple[float, ...]


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

    def upsert(
        self,
        *,
        chunks: Sequence[ChildChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseEmbedding],
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
