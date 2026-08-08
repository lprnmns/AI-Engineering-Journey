"""Tests for dense, sparse and hybrid retrieval orchestration."""

from collections.abc import Sequence
from dataclasses import replace

from projects.document_intelligence_service.app.application.retrieval_service import (
    RetrievalService,
)
from projects.document_intelligence_service.app.domain.entities import RetrievalMode
from projects.document_intelligence_service.app.domain.retrieval import RetrievedChunk
from projects.document_intelligence_service.app.domain.vectors import SparseVector


def candidate(source_id: str) -> RetrievedChunk:
    """Create a compact candidate fixture."""

    return RetrievedChunk(
        source_id=source_id,
        document_id="doc-1",
        version_id="ver-1",
        parent_id="parent-1",
        title="RAG",
        text=f"text-{source_id}",
        page_start=1,
        page_end=1,
        score=0.5,
        rank=1,
    )


class FakeDenseEmbedder:
    """Return one deterministic query vector."""

    dimension = 2

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class FakeSparseEmbedder:
    """Return one deterministic query sparse vector."""

    def embed_documents(self, texts: Sequence[str]) -> tuple[SparseVector, ...]:
        return tuple(SparseVector(indices=(1,), values=(1.0,)) for _ in texts)


class FakeRetriever:
    """Expose intentionally different dense and sparse rankings."""

    def search_dense(
        self,
        *,
        query_vector: Sequence[float],
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        del query_vector, limit, document_ids
        return (candidate("dense-top"), candidate("shared"))

    def search_sparse(
        self,
        *,
        query_vector: SparseVector,
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        del query_vector, limit, document_ids
        return (candidate("shared"), candidate("sparse-only"))


class FakeReranker:
    """Reverse candidates to prove the optional rerank stage is used."""

    def __init__(self) -> None:
        self.seen_count = 0

    def rerank(
        self,
        *,
        question: str,
        candidates: Sequence[RetrievedChunk],
        limit: int,
    ) -> tuple[RetrievedChunk, ...]:
        del question
        self.seen_count = len(candidates)
        return tuple(
            replace(candidate, score=1.0, rerank_score=1.0, rank=index)
            for index, candidate in enumerate(
                tuple(candidates)[::-1][:limit], start=1
            )
        )


def make_service(reranker: FakeReranker | None = None) -> RetrievalService:
    """Build the service with fake infrastructure ports."""

    return RetrievalService(
        dense_embedder=FakeDenseEmbedder(),
        sparse_embedder=FakeSparseEmbedder(),
        retriever=FakeRetriever(),
        candidate_limit=30,
        rrf_k=60,
        fusion_limit=20,
        reranker=reranker,
    )


def test_dense_mode_returns_only_dense_candidates() -> None:
    result = make_service().search(
        question="Qdrant ne işe yarar?",
        mode=RetrievalMode.DENSE,
        top_k=1,
    )

    assert result.mode == "dense"
    assert result.dense_candidates == 2
    assert result.sparse_candidates == 0
    assert result.rrf_candidates == 0
    assert [item.source_id for item in result.candidates] == ["dense-top"]


def test_hybrid_mode_uses_rank_based_rrf_not_raw_score_addition() -> None:
    result = make_service().search(
        question="Qdrant ne işe yarar?",
        mode=RetrievalMode.HYBRID,
        top_k=3,
    )

    assert result.dense_candidates == 2
    assert result.sparse_candidates == 2
    assert result.rrf_candidates == 3
    assert [item.source_id for item in result.candidates] == [
        "shared",
        "dense-top",
        "sparse-only",
    ]
    assert result.candidates[0].dense_rank == 2
    assert result.candidates[0].sparse_rank == 1
    assert result.candidates[0].fused_score is not None


def test_optional_reranker_receives_fused_candidates_and_returns_final_window() -> None:
    reranker = FakeReranker()
    result = make_service(reranker).search(
        question="Qdrant ne işe yarar?",
        mode=RetrievalMode.HYBRID,
        top_k=2,
    )

    assert reranker.seen_count == 3
    assert result.reranked_candidates == 2
    assert [item.source_id for item in result.candidates] == [
        "sparse-only",
        "dense-top",
    ]
    assert result.candidates[0].rerank_score == 1.0
