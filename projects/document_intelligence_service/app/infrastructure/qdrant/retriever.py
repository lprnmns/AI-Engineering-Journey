"""Qdrant dense and sparse retrieval adapter."""

from collections.abc import Sequence
from typing import Any, cast

from qdrant_client import QdrantClient, models

from ...domain.retrieval import RetrievedChunk
from ...domain.vectors import SparseVector
from .schema import QdrantSchema, QdrantSchemaManager


class QdrantRetriever:
    """Search only active Qdrant points and restore source metadata."""

    def __init__(self, client: QdrantClient, schema: QdrantSchema) -> None:
        self._client = client
        self._schema_manager = QdrantSchemaManager(client, schema)

    def search_dense(
        self,
        *,
        query_vector: Sequence[float],
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        """Run cosine search on the named dense vector."""

        self._validate_limit(limit)
        self._schema_manager.ensure_collection()
        response = self._client.query_points(
            collection_name=self._schema_manager.schema.collection_name,
            query=list(query_vector),
            using=self._schema_manager.schema.dense_name,
            query_filter=self._active_filter(document_ids),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return tuple(
            self._map_point(point, rank=index)
            for index, point in enumerate(response.points, start=1)
        )

    def search_sparse(
        self,
        *,
        query_vector: SparseVector,
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        """Run lexical search on the named IDF sparse vector."""

        self._validate_limit(limit)
        self._schema_manager.ensure_collection()
        response = self._client.query_points(
            collection_name=self._schema_manager.schema.collection_name,
            query=models.SparseVector(
                indices=list(query_vector.indices),
                values=list(query_vector.values),
            ),
            using=self._schema_manager.schema.sparse_name,
            query_filter=self._active_filter(document_ids),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return tuple(
            self._map_point(point, rank=index)
            for index, point in enumerate(response.points, start=1)
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit <= 0 or limit > 50:
            raise ValueError("retrieval limit must be between 1 and 50")

    @staticmethod
    def _active_filter(document_ids: Sequence[str]) -> models.Filter:
        active_condition = models.FieldCondition(
            key="is_active",
            match=models.MatchValue(value=True),
        )
        normalized_ids = tuple(dict.fromkeys(document_id for document_id in document_ids if document_id))
        if normalized_ids:
            return models.Filter(
                must=[
                    active_condition,
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchAny(any=list(normalized_ids)),
                    ),
                ]
            )
        return models.Filter(must=active_condition)

    @classmethod
    def _map_point(cls, point: models.ScoredPoint, *, rank: int) -> RetrievedChunk:
        payload = cast(dict[str, Any], point.payload or {})
        return RetrievedChunk(
            source_id=cls._required_string(payload, "chunk_id"),
            document_id=cls._required_string(payload, "document_id"),
            version_id=cls._required_string(payload, "version_id"),
            parent_id=cls._required_string(payload, "parent_id"),
            title=cls._optional_string(payload, "title"),
            text=cls._required_string(payload, "text"),
            page_start=cls._required_int(payload, "page_start"),
            page_end=cls._required_int(payload, "page_end"),
            score=float(point.score),
            rank=rank,
        )

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Qdrant payload field {key!r} must be a non-empty string")
        return value

    @staticmethod
    def _optional_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        return value if isinstance(value, str) else ""

    @staticmethod
    def _required_int(payload: dict[str, Any], key: str) -> int:
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Qdrant payload field {key!r} must be an integer")
        return value
