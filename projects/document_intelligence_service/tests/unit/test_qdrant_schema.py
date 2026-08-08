"""Unit tests for named-vector Qdrant schema and point mapping."""

import pytest
from qdrant_client import QdrantClient, models

from projects.document_intelligence_service.app.domain.chunks import ChildChunk
from projects.document_intelligence_service.app.infrastructure.qdrant.chunk_store import (
    QdrantChunkStore,
    SparseEmbedding,
)
from projects.document_intelligence_service.app.infrastructure.qdrant.retriever import (
    QdrantRetriever,
)
from projects.document_intelligence_service.app.infrastructure.qdrant.schema import (
    QdrantSchema,
    QdrantSchemaError,
    QdrantSchemaManager,
)


def make_chunk(
    chunk_id: str = "chunk-1",
    *,
    document_id: str = "doc-1",
    version_id: str = "ver-1",
) -> ChildChunk:
    """Create a deterministic child chunk fixture."""

    return ChildChunk(
        chunk_id=chunk_id,
        parent_id=f"{document_id}:{version_id}:parent:000",
        document_id=document_id,
        version_id=version_id,
        source="guide.pdf",
        title="RAG",
        text="Qdrant kanıt adaylarını saklar.",
        chunk_index=1,
        page_start=2,
        page_end=2,
        token_count_estimate=5,
        text_hash="a" * 64,
    )


def make_store(dense_size: int = 2) -> QdrantChunkStore:
    """Create an isolated in-memory Qdrant store."""

    schema = QdrantSchema(
        collection_name="test_named_vectors",
        dense_size=dense_size,
    )
    return QdrantChunkStore(QdrantClient(":memory:"), schema)


@pytest.mark.filterwarnings("ignore:Payload indexes have no effect in the local Qdrant")
def test_schema_creates_named_dense_and_sparse_vectors() -> None:
    client = QdrantClient(":memory:")
    schema = QdrantSchema(collection_name="schema_test", dense_size=2)
    manager = QdrantSchemaManager(client, schema)

    manager.ensure_collection()
    info = client.get_collection("schema_test")

    assert isinstance(info.config.params.vectors, dict)
    assert "dense" in info.config.params.vectors
    assert isinstance(info.config.params.sparse_vectors, dict)
    assert "sparse" in info.config.params.sparse_vectors
    assert info.config.params.vectors["dense"].size == 2


def test_point_id_is_stable_for_same_version_and_chunk() -> None:
    first = QdrantChunkStore.point_id("ver-1", "chunk-1")
    second = QdrantChunkStore.point_id("ver-1", "chunk-1")
    different_version = QdrantChunkStore.point_id("ver-2", "chunk-1")

    assert first == second
    assert first != different_version


def test_upsert_stores_named_vectors_and_payload() -> None:
    store = make_store()
    chunk = make_chunk()
    sparse = SparseEmbedding(indices=(1, 4), values=(0.8, 0.2))

    store.upsert(
        chunks=[chunk],
        dense_vectors=[(1.0, 0.0)],
        sparse_vectors=[sparse],
        pipeline_fingerprint="pipe-1",
        language="tr",
        is_active=False,
    )
    store.upsert(
        chunks=[chunk],
        dense_vectors=[(1.0, 0.0)],
        sparse_vectors=[sparse],
        pipeline_fingerprint="pipe-1",
        language="tr",
        is_active=True,
    )

    client_info = store.client.count(store.collection_name, exact=True)
    point = store.client.retrieve(
        collection_name=store.collection_name,
        ids=[store.point_id("ver-1", "chunk-1")],
        with_vectors=True,
    )[0]
    assert client_info.count == 1
    assert point.payload is not None
    assert point.payload["page_start"] == 2
    assert point.payload["is_active"] is True
    assert isinstance(point.vector, dict)


def test_upsert_rejects_dense_dimension_mismatch() -> None:
    store = make_store(dense_size=3)

    with pytest.raises(ValueError, match="expected 3"):
        store.upsert(
            chunks=[make_chunk()],
            dense_vectors=[(1.0, 0.0)],
            sparse_vectors=[SparseEmbedding((1,), (1.0,))],
            pipeline_fingerprint="pipe-1",
        )


def test_upsert_rejects_misaligned_sparse_values() -> None:
    store = make_store()

    with pytest.raises(ValueError, match="equal lengths"):
        store.upsert(
            chunks=[make_chunk()],
            dense_vectors=[(1.0, 0.0)],
            sparse_vectors=[SparseEmbedding((1, 2), (1.0,))],
            pipeline_fingerprint="pipe-1",
        )


def test_existing_dense_dimension_mismatch_fails_startup_validation() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="mismatch",
        vectors_config={
            "dense": models.VectorParams(size=2, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    manager = QdrantSchemaManager(
        client,
        QdrantSchema(collection_name="mismatch", dense_size=3),
    )

    with pytest.raises(QdrantSchemaError, match="dimension"):
        manager.ensure_collection()


def test_stage_verify_activate_hides_previous_version() -> None:
    store = make_store()
    sparse = SparseEmbedding(indices=(1, 4), values=(0.8, 0.2))

    first = make_chunk(version_id="ver-1")
    store.stage_version(
        chunks=[first],
        dense_vectors=[(1.0, 0.0)],
        sparse_vectors=[sparse],
        pipeline_fingerprint="pipe-1",
        language="tr",
    )
    first_verification = store.verify_version(
        document_id="doc-1",
        version_id="ver-1",
        expected_chunk_count=1,
    )
    assert first_verification.is_valid
    store.activate_version(
        document_id="doc-1",
        version_id="ver-1",
        verification=first_verification,
    )

    second = make_chunk(version_id="ver-2")
    store.stage_version(
        chunks=[second],
        dense_vectors=[(0.0, 1.0)],
        sparse_vectors=[sparse],
        pipeline_fingerprint="pipe-2",
        language="tr",
    )
    second_verification = store.verify_version(
        document_id="doc-1",
        version_id="ver-2",
        expected_chunk_count=1,
    )
    assert second_verification.is_valid
    store.activate_version(
        document_id="doc-1",
        version_id="ver-2",
        verification=second_verification,
    )

    first_point = store.client.retrieve(
        collection_name=store.collection_name,
        ids=[store.point_id("ver-1", "chunk-1")],
    )[0]
    second_point = store.client.retrieve(
        collection_name=store.collection_name,
        ids=[store.point_id("ver-2", "chunk-1")],
    )[0]
    assert first_point.payload is not None
    assert second_point.payload is not None
    assert first_point.payload["is_active"] is False
    assert second_point.payload["is_active"] is True


def test_retriever_searches_active_named_dense_and_sparse_vectors() -> None:
    schema = QdrantSchema(collection_name="retrieval_test", dense_size=2)
    store = QdrantChunkStore(QdrantClient(":memory:"), schema)
    chunk = make_chunk()
    sparse = SparseEmbedding(indices=(1, 4), values=(0.8, 0.2))
    store.stage_version(
        chunks=[chunk],
        dense_vectors=[(1.0, 0.0)],
        sparse_vectors=[sparse],
        pipeline_fingerprint="pipe-1",
        language="tr",
    )
    verification = store.verify_version(
        document_id="doc-1",
        version_id="ver-1",
        expected_chunk_count=1,
    )
    store.activate_version(
        document_id="doc-1",
        version_id="ver-1",
        verification=verification,
    )
    retriever = QdrantRetriever(store.client, schema)

    dense_hits = retriever.search_dense(
        query_vector=(1.0, 0.0),
        limit=5,
        document_ids=("doc-1",),
    )
    sparse_hits = retriever.search_sparse(
        query_vector=sparse,
        limit=5,
        document_ids=("doc-1",),
    )

    assert len(dense_hits) == 1
    assert len(sparse_hits) == 1
    assert dense_hits[0].source_id == "chunk-1"
    assert sparse_hits[0].page_start == 2
