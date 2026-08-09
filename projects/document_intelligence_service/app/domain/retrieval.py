"""Framework-independent retrieval evidence models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """One child chunk returned by a dense, sparse or fused retriever."""

    source_id: str
    document_id: str
    version_id: str
    parent_id: str
    title: str
    text: str
    page_start: int
    page_end: int
    score: float
    rank: int
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    dense_score: float | None = None
    sparse_score: float | None = None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Candidates and trace counts produced before reranking or generation."""

    mode: str
    candidates: tuple[RetrievedChunk, ...]
    dense_candidates: int
    sparse_candidates: int
    rrf_candidates: int
    embedding_ms: float
    search_ms: float
    reranked_candidates: int = 0
    rerank_ms: float = 0.0
    candidate_window: tuple[RetrievedChunk, ...] = ()
