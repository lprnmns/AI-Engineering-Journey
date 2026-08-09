"""Dense, sparse and hybrid retrieval orchestration."""

from dataclasses import dataclass, replace
from collections.abc import Sequence
from time import perf_counter

from ..domain.entities import RetrievalMode
from ..domain.retrieval import RetrievedChunk, RetrievalResult
from ..domain.vectors import SparseVector
from .ports import ChunkRetriever, DenseEmbedder, Reranker, SparseEmbedder


@dataclass(slots=True)
class _FusionEntry:
    """Mutable application-local state while rank lists are fused."""

    candidate: RetrievedChunk
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0
    dense_score: float | None = None
    sparse_score: float | None = None


class RetrievalService:
    """Coordinate query encoding, bounded candidate search and RRF fusion."""

    def __init__(
        self,
        *,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
        retriever: ChunkRetriever,
        candidate_limit: int = 30,
        rrf_k: int = 60,
        fusion_limit: int = 20,
        reranker: Reranker | None = None,
        rerank_limit: int = 5,
    ) -> None:
        if (
            candidate_limit <= 0
            or rrf_k <= 0
            or fusion_limit <= 0
            or rerank_limit <= 0
        ):
            raise ValueError("retrieval limits must be greater than zero")
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._retriever = retriever
        self._candidate_limit = min(candidate_limit, 50)
        self._rrf_k = rrf_k
        self._fusion_limit = min(fusion_limit, 50)
        self._reranker = reranker
        self._rerank_limit = min(rerank_limit, self._fusion_limit)

    def search(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        top_k: int,
        document_ids: Sequence[str] = (),
    ) -> RetrievalResult:
        """Search active evidence with one of the three supported modes."""

        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        embedding_started = perf_counter()
        dense_vector: tuple[float, ...] | None = None
        sparse_vector: SparseVector | None = None
        if mode in (RetrievalMode.DENSE, RetrievalMode.HYBRID):
            dense_vector = self._one_dense_vector(normalized_question)
        if mode in (RetrievalMode.BM25, RetrievalMode.HYBRID):
            sparse_vector = self._one_sparse_vector(normalized_question)
        embedding_ms = (perf_counter() - embedding_started) * 1000

        search_started = perf_counter()
        limit = min(max(self._candidate_limit, top_k), 50)
        dense_candidates: tuple[RetrievedChunk, ...] = ()
        sparse_candidates: tuple[RetrievedChunk, ...] = ()
        if dense_vector is not None:
            dense_candidates = self._retriever.search_dense(
                query_vector=dense_vector,
                limit=limit,
                document_ids=document_ids,
            )
        if sparse_vector is not None:
            sparse_candidates = self._retriever.search_sparse(
                query_vector=sparse_vector,
                limit=limit,
                document_ids=document_ids,
            )

        if mode is RetrievalMode.HYBRID:
            candidates, rrf_count = self._fuse(
                dense_candidates,
                sparse_candidates,
                top_k=top_k,
            )
        elif mode is RetrievalMode.DENSE:
            window = self._candidate_window(top_k)
            candidates = tuple(
                replace(
                    candidate,
                    rank=index,
                    dense_score=(
                        candidate.dense_score
                        if candidate.dense_score is not None
                        else candidate.score
                    ),
                )
                for index, candidate in enumerate(dense_candidates[:window], start=1)
            )
            rrf_count = 0
        else:
            window = self._candidate_window(top_k)
            candidates = tuple(
                replace(
                    candidate,
                    rank=index,
                    sparse_score=(
                        candidate.sparse_score
                        if candidate.sparse_score is not None
                        else candidate.score
                    ),
                )
                for index, candidate in enumerate(sparse_candidates[:window], start=1)
            )
            rrf_count = 0
        search_ms = (perf_counter() - search_started) * 1000
        candidate_window = candidates
        reranked_count = 0
        rerank_ms = 0.0
        if self._reranker is not None and candidates:
            rerank_started = perf_counter()
            candidates = self._reranker.rerank(
                question=normalized_question,
                candidates=candidates,
                limit=min(top_k, self._rerank_limit),
            )
            rerank_ms = (perf_counter() - rerank_started) * 1000
            reranked_count = len(candidates)
        else:
            candidates = candidates[:top_k]

        return RetrievalResult(
            mode=mode.value,
            candidates=candidates,
            dense_candidates=len(dense_candidates),
            sparse_candidates=len(sparse_candidates),
            rrf_candidates=rrf_count,
            embedding_ms=embedding_ms,
            search_ms=search_ms,
            reranked_candidates=reranked_count,
            rerank_ms=rerank_ms,
            candidate_window=candidate_window,
        )

    def _candidate_window(self, top_k: int) -> int:
        """Keep a bounded candidate window separate from final top-k."""

        return min(max(top_k, self._fusion_limit), 50)

    def _one_dense_vector(self, question: str) -> tuple[float, ...]:
        vectors = self._dense_embedder.embed_documents((question,))
        if len(vectors) != 1:
            raise ValueError("dense embedder returned an unexpected query batch")
        return vectors[0]

    def _one_sparse_vector(self, question: str) -> SparseVector:
        vectors = self._sparse_embedder.embed_documents((question,))
        if len(vectors) != 1:
            raise ValueError("sparse embedder returned an unexpected query batch")
        return vectors[0]

    def _fuse(
        self,
        dense_candidates: Sequence[RetrievedChunk],
        sparse_candidates: Sequence[RetrievedChunk],
        *,
        top_k: int,
    ) -> tuple[tuple[RetrievedChunk, ...], int]:
        entries: dict[str, _FusionEntry] = {}
        for rank, candidate in enumerate(dense_candidates, start=1):
            entry = entries.setdefault(
                candidate.source_id,
                _FusionEntry(candidate=candidate),
            )
            entry.dense_rank = rank
            entry.dense_score = (
                candidate.dense_score
                if candidate.dense_score is not None
                else candidate.score
            )
            entry.fused_score += 1.0 / (self._rrf_k + rank)
        for rank, candidate in enumerate(sparse_candidates, start=1):
            entry = entries.setdefault(
                candidate.source_id,
                _FusionEntry(candidate=candidate),
            )
            entry.sparse_rank = rank
            entry.sparse_score = (
                candidate.sparse_score
                if candidate.sparse_score is not None
                else candidate.score
            )
            entry.fused_score += 1.0 / (self._rrf_k + rank)

        limit = self._candidate_window(top_k)
        ordered = sorted(
            entries.values(),
            key=lambda entry: (-entry.fused_score, entry.candidate.source_id),
        )[:limit]
        fused = tuple(
            replace(
                entry.candidate,
                score=entry.fused_score,
                fused_score=entry.fused_score,
                rank=index,
                dense_rank=entry.dense_rank,
                sparse_rank=entry.sparse_rank,
                dense_score=entry.dense_score,
                sparse_score=entry.sparse_score,
            )
            for index, entry in enumerate(ordered, start=1)
        )
        return fused, len(entries)
