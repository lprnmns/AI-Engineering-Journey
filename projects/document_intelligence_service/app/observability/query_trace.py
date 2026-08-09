"""Structured, privacy-conscious query trace events."""

from dataclasses import dataclass
import hashlib
import json
import logging
from typing import Protocol

from ..domain.evidence_validation import EvidenceWarning
from ..domain.entities import Decision, NoAnswerReason
from ..domain.retrieval import RetrievalResult
from .request_id import get_request_id


@dataclass(frozen=True, slots=True)
class QueryTraceEvent:
    """One JSON-serializable event for a completed RAG query."""

    event: str
    request_id: str
    question_sha256: str
    decision: Decision
    no_answer_reason: NoAnswerReason | None
    retrieval_mode: str
    dense_candidates: int
    sparse_candidates: int
    rrf_candidates: int
    reranked_candidates: int
    selected_evidence_count: int
    top_score: float | None
    score_margin: float | None
    coverage_ratio: float
    provider: str | None
    model: str | None
    warning_codes: tuple[str, ...]
    embedding_ms: float
    search_ms: float
    rerank_ms: float
    llm_ms: float
    total_ms: float

    @classmethod
    def from_query_result(
        cls,
        *,
        question: str,
        decision: Decision,
        no_answer_reason: NoAnswerReason | None,
        retrieval: RetrievalResult,
        selected_evidence_count: int,
        top_score: float | None,
        score_margin: float | None,
        coverage_ratio: float,
        provider: str | None,
        model: str | None,
        warnings: tuple[EvidenceWarning, ...],
        llm_ms: float,
        total_ms: float,
    ) -> "QueryTraceEvent":
        """Build an event without retaining the raw user question."""

        return cls(
            event="rag_query",
            request_id=get_request_id(),
            question_sha256=hashlib.sha256(
                question.encode("utf-8")
            ).hexdigest(),
            decision=decision,
            no_answer_reason=no_answer_reason,
            retrieval_mode=retrieval.mode,
            dense_candidates=retrieval.dense_candidates,
            sparse_candidates=retrieval.sparse_candidates,
            rrf_candidates=retrieval.rrf_candidates,
            reranked_candidates=retrieval.reranked_candidates,
            selected_evidence_count=selected_evidence_count,
            top_score=top_score,
            score_margin=score_margin,
            coverage_ratio=coverage_ratio,
            provider=provider,
            model=model,
            warning_codes=tuple(warning.code.value for warning in warnings),
            embedding_ms=retrieval.embedding_ms,
            search_ms=retrieval.search_ms,
            rerank_ms=retrieval.rerank_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe mapping for log sinks and tests."""

        return {
            "event": self.event,
            "request_id": self.request_id,
            "question_sha256": self.question_sha256,
            "decision": self.decision.value,
            "no_answer_reason": (
                self.no_answer_reason.value
                if self.no_answer_reason is not None
                else None
            ),
            "retrieval": {
                "mode": self.retrieval_mode,
                "dense_candidates": self.dense_candidates,
                "sparse_candidates": self.sparse_candidates,
                "rrf_candidates": self.rrf_candidates,
                "reranked_candidates": self.reranked_candidates,
                "selected_evidence_count": self.selected_evidence_count,
            },
            "answerability": {
                "top_score": self.top_score,
                "score_margin": self.score_margin,
                "coverage_ratio": self.coverage_ratio,
            },
            "model": {"provider": self.provider, "name": self.model},
            "warning_codes": list(self.warning_codes),
            "latency_ms": {
                "embedding": self.embedding_ms,
                "search": self.search_ms,
                "rerank": self.rerank_ms,
                "llm": self.llm_ms,
                "total": self.total_ms,
            },
        }


class QueryTraceSink(Protocol):
    """Application boundary for query observability sinks."""

    def record(self, event: QueryTraceEvent) -> None:
        """Persist or forward one completed query event."""


class JsonQueryTraceSink:
    """Write one compact JSON object per query to a standard logger."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(
            "document_intelligence_service.query"
        )

    def record(self, event: QueryTraceEvent) -> None:
        """Emit structured JSON without logging the raw question or evidence."""

        self._logger.info(
            "%s",
            json.dumps(
                event.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
