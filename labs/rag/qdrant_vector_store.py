from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

from qdrant_client import QdrantClient, models

from labs.rag.chunking import Chunk, ChunkSearchResult
from labs.rag.dense_vector_store import DenseTextVectorizer
from labs.rag.dense_vectorizer import DenseVectorizer


DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
DEFAULT_COLLECTION_NAME = "mentor_program_pdf_v1"
DEFAULT_VECTOR_SIZE = 384
INGESTION_VERSION = "mentor-program-section-aware-v1"


@dataclass(frozen=True)
class QdrantStoreStats:
    collection_name: str
    point_count: int
    vector_size: int


class QdrantVectorStore:
    """Persistent dense retrieval backed by a Qdrant collection."""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        client: QdrantClient | None = None,
        vectorizer: DenseTextVectorizer | None = None,
        vector_size: int = DEFAULT_VECTOR_SIZE,
    ) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be greater than zero")

        self._collection_name = collection_name
        self._client = client or QdrantClient(url=DEFAULT_QDRANT_URL)
        self._vectorizer = vectorizer or DenseVectorizer()
        self._vector_size = vector_size

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection_name):
            collection = self._client.get_collection(self._collection_name)
            vector_config = collection.config.params.vectors
            if not isinstance(vector_config, models.VectorParams):
                raise RuntimeError("named Qdrant vectors are not supported by this store")
            if vector_config.size != self._vector_size:
                raise RuntimeError(
                    "existing collection vector size does not match the configured vector size"
                )
            return

        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=models.VectorParams(
                size=self._vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    @staticmethod
    def point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-engineering-journey/{chunk_id}"))

    @staticmethod
    def payload(chunk: Chunk) -> dict[str, str | int]:
        return {
            "chunk_id": chunk.chunk_id,
            "section_id": chunk.doc_id,
            "section_title": chunk.title,
            "text": chunk.text,
            "source": chunk.source,
            "chunk_index": chunk.chunk_index,
            "ingestion_version": INGESTION_VERSION,
        }

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return

        self.ensure_collection()
        points = []
        for chunk in chunks:
            vector = self._vectorizer.vectorize(f"{chunk.title} {chunk.text}")
            if len(vector) != self._vector_size:
                raise ValueError(
                    f"chunk {chunk.chunk_id} has vector size {len(vector)}, "
                    f"expected {self._vector_size}"
                )
            points.append(
                models.PointStruct(
                    id=self.point_id(chunk.chunk_id),
                    vector=vector,
                    payload=self.payload(chunk),
                )
            )

        self._client.upsert(collection_name=self._collection_name, points=points, wait=True)

    def search(
        self,
        query: str,
        top_k: int = 3,
        section_id: str | None = None,
    ) -> list[ChunkSearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        query_filter = None
        if section_id is not None:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="section_id",
                        match=models.MatchValue(value=section_id),
                    )
                ]
            )

        query_vector = self._vectorizer.vectorize(query)
        if len(query_vector) != self._vector_size:
            raise ValueError(
                f"query vector size {len(query_vector)} does not match {self._vector_size}"
            )

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        results: list[ChunkSearchResult] = []
        for point in response.points:
            payload = cast(dict[str, Any], point.payload or {})
            results.append(
                ChunkSearchResult(
                    chunk_id=str(payload["chunk_id"]),
                    doc_id=str(payload["section_id"]),
                    title=str(payload["section_title"]),
                    text=str(payload["text"]),
                    source=str(payload["source"]),
                    chunk_index=int(payload["chunk_index"]),
                    score=float(point.score),
                )
            )
        return results

    def stats(self) -> QdrantStoreStats:
        self.ensure_collection()
        count = self._client.count(collection_name=self._collection_name, exact=True).count
        return QdrantStoreStats(
            collection_name=self._collection_name,
            point_count=count,
            vector_size=self._vector_size,
        )
