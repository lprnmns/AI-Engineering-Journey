"""Qdrant named-vector collection schema."""

from dataclasses import dataclass
from qdrant_client import QdrantClient, models


class QdrantSchemaError(RuntimeError):
    """Raised when an existing collection cannot serve this application."""


@dataclass(frozen=True, slots=True)
class QdrantSchema:
    """Expected dense/sparse vectors and indexed payload fields."""

    collection_name: str = "document_chunks_v2_bm25"
    dense_name: str = "dense"
    sparse_name: str = "sparse"
    dense_size: int = 384
    payload_indexes: tuple[tuple[str, models.PayloadSchemaType], ...] = (
        ("document_id", models.PayloadSchemaType.KEYWORD),
        ("version_id", models.PayloadSchemaType.KEYWORD),
        ("parent_id", models.PayloadSchemaType.KEYWORD),
        ("source", models.PayloadSchemaType.KEYWORD),
        ("language", models.PayloadSchemaType.KEYWORD),
        ("tenant_id", models.PayloadSchemaType.KEYWORD),
        ("acl_tags", models.PayloadSchemaType.KEYWORD),
        ("page_start", models.PayloadSchemaType.INTEGER),
        ("page_end", models.PayloadSchemaType.INTEGER),
        ("is_active", models.PayloadSchemaType.BOOL),
    )

    def __post_init__(self) -> None:
        if self.dense_size <= 0:
            raise ValueError("dense_size must be greater than zero")


class QdrantSchemaManager:
    """Create and validate the collection before ingestion or query."""

    def __init__(self, client: QdrantClient, schema: QdrantSchema) -> None:
        self._client = client
        self._schema = schema

    @property
    def schema(self) -> QdrantSchema:
        """Return the expected schema."""

        return self._schema

    def ensure_collection(self) -> None:
        """Create the named-vector collection or validate the existing one."""

        if self._client.collection_exists(self._schema.collection_name):
            self._validate_existing_collection()
            return

        self._client.create_collection(
            collection_name=self._schema.collection_name,
            vectors_config={
                self._schema.dense_name: models.VectorParams(
                    size=self._schema.dense_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self._schema.sparse_name: models.SparseVectorParams(
                    modifier=models.Modifier.IDF
                )
            },
        )
        for field_name, field_schema in self._schema.payload_indexes:
            self._client.create_payload_index(
                collection_name=self._schema.collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )

    def _validate_existing_collection(self) -> None:
        info = self._client.get_collection(self._schema.collection_name)
        vector_config = info.config.params.vectors
        sparse_config = info.config.params.sparse_vectors
        if not isinstance(vector_config, dict):
            raise QdrantSchemaError("existing collection does not use named dense vectors")
        dense_config = vector_config.get(self._schema.dense_name)
        if dense_config is None or dense_config.size != self._schema.dense_size:
            raise QdrantSchemaError("existing dense vector dimension does not match")
        if not isinstance(sparse_config, dict) or self._schema.sparse_name not in sparse_config:
            raise QdrantSchemaError("existing collection is missing the sparse vector")
        sparse_params = sparse_config[self._schema.sparse_name]
        if sparse_params.modifier is not models.Modifier.IDF:
            raise QdrantSchemaError("existing sparse vector must use Qdrant IDF for BM25")

    def collection_info(self) -> models.CollectionInfo:
        """Return validated collection information for startup diagnostics."""

        self.ensure_collection()
        return self._client.get_collection(self._schema.collection_name)
