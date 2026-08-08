"""Unit tests for lazy dense and deterministic sparse embedding adapters."""

from projects.document_intelligence_service.app.infrastructure.embeddings.sparse import (
    HashingSparseEncoder,
)


def test_hashing_sparse_encoder_is_stable_and_sorted() -> None:
    encoder = HashingSparseEncoder(feature_count=128)

    first = encoder.embed_documents(("Qdrant Türkçe arama",))[0]
    second = encoder.embed_documents(("Qdrant Türkçe arama",))[0]

    assert first == second
    assert first.indices == tuple(sorted(first.indices))
    assert len(first.indices) == len(set(first.indices))
    assert all(value > 0 for value in first.values)


def test_hashing_sparse_encoder_counts_repeated_terms() -> None:
    encoder = HashingSparseEncoder(feature_count=128)

    repeated = encoder.embed_documents(("qdrant qdrant",))[0]
    single = encoder.embed_documents(("qdrant",))[0]

    assert repeated.indices == single.indices
    assert repeated.values[0] > single.values[0]
