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
    parent_text: str | None = None
    tenant_id: str = "default"
    acl_tags: tuple[str, ...] = ("public",)

    @property
    def context_text(self) -> str:
        """Return expanded parent context when the adapter supplied it."""

        return self.parent_text or self.text


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
    debug_candidates: tuple["RetrievalDebugCandidate", ...] = ()
    candidate_limit: int = 0
    fusion_limit: int = 0
    rerank_limit: int = 0


@dataclass(frozen=True, slots=True)
class RetrievalDebugCandidate:
    """Safe rank/score trace for one bounded retrieval candidate."""

    source_id: str
    retrieval_rank: int | None
    rerank_rank: int | None
    dense_rank: int | None
    sparse_rank: int | None
    dense_score: float | None
    sparse_score: float | None
    fused_score: float | None
    rerank_score: float | None
    matched_terms: tuple[str, ...]
