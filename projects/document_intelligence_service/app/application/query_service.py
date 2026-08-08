"""Query orchestration: retrieve, gate, then optionally generate."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
import re
from time import perf_counter

from ..domain.answerability import (
    AnswerabilityDecision,
    AnswerabilityPolicy,
    AnswerabilitySignals,
)
from ..domain.entities import Decision, NoAnswerReason, RetrievalMode
from ..domain.errors import ErrorCode, ServiceError
from ..domain.generation import AnswerGenerationError
from ..domain.retrieval import RetrievedChunk, RetrievalResult
from .ports import AnswerGenerator
from .retrieval_service import RetrievalService


@dataclass(frozen=True, slots=True)
class QueryExecutionResult:
    """Application result mapped to the public query response by the API."""

    decision: Decision
    answer: str | None
    no_answer_reason: NoAnswerReason | None
    sources: tuple[RetrievedChunk, ...]
    retrieval: RetrievalResult
    provider: str | None
    model: str | None
    llm_ms: float
    total_ms: float
    answerability: AnswerabilityDecision


class QueryService:
    """Coordinate retrieval, pre-LLM rejection and grounded generation."""

    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        answerability: AnswerabilityPolicy,
        answer_generator: AnswerGenerator,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._answerability = answerability
        self._answer_generator = answer_generator

    async def execute(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        top_k: int,
        document_ids: Sequence[str] = (),
    ) -> QueryExecutionResult:
        """Run the bounded query sequence and skip generation when unsafe."""

        started = perf_counter()
        retrieval = await asyncio.to_thread(
            self._retrieval_service.search,
            question=question,
            mode=mode,
            top_k=top_k,
            document_ids=document_ids,
        )
        signals, score_kind = self._signals(question, retrieval)
        gate = self._answerability.decide(
            signals=signals,
            score_kind=score_kind,
        )
        if gate.decision is Decision.NO_ANSWER:
            return QueryExecutionResult(
                decision=gate.decision,
                answer=None,
                no_answer_reason=gate.reason,
                sources=(),
                retrieval=retrieval,
                provider=None,
                model=None,
                llm_ms=0.0,
                total_ms=(perf_counter() - started) * 1000,
                answerability=gate,
            )

        try:
            generated = await self._answer_generator.generate(
                question=question,
                evidence=retrieval.candidates,
            )
        except AnswerGenerationError as exc:
            raise ServiceError(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message="Answer generation dependency is unavailable",
            ) from exc
        return QueryExecutionResult(
            decision=Decision.ANSWERED,
            answer=generated.answer,
            no_answer_reason=None,
            sources=retrieval.candidates,
            retrieval=retrieval,
            provider=generated.provider,
            model=generated.model,
            llm_ms=generated.latency_ms,
            total_ms=(perf_counter() - started) * 1000,
            answerability=gate,
        )

    def _signals(
        self,
        question: str,
        retrieval: RetrievalResult,
    ) -> tuple[AnswerabilitySignals, str]:
        """Extract comparable score and coverage signals from retrieval trace."""

        score_kind = self._score_kind(retrieval)
        scores = tuple(
            self._score_for(candidate, score_kind)
            for candidate in retrieval.candidates
        )
        top_score = scores[0] if scores else None
        margin = scores[0] - scores[1] if len(scores) > 1 else None
        return (
            AnswerabilitySignals(
                evidence_count=len(retrieval.candidates),
                top_score=top_score,
                score_margin=margin,
                coverage_ratio=self._coverage_ratio(
                    question,
                    retrieval.candidates,
                ),
            ),
            score_kind,
        )

    @staticmethod
    def _score_kind(retrieval: RetrievalResult) -> str:
        if any(candidate.rerank_score is not None for candidate in retrieval.candidates):
            return "rerank"
        if retrieval.mode == RetrievalMode.BM25.value:
            return "sparse"
        if retrieval.mode == RetrievalMode.DENSE.value:
            return "dense"
        if any(candidate.dense_score is not None for candidate in retrieval.candidates):
            return "dense"
        return "sparse"

    @staticmethod
    def _score_for(candidate: RetrievedChunk, score_kind: str) -> float:
        if score_kind == "rerank" and candidate.rerank_score is not None:
            return candidate.rerank_score
        if score_kind == "sparse" and candidate.sparse_score is not None:
            return candidate.sparse_score
        if score_kind == "dense" and candidate.dense_score is not None:
            return candidate.dense_score
        return candidate.score

    @staticmethod
    def _coverage_ratio(
        question: str,
        candidates: Sequence[RetrievedChunk],
    ) -> float:
        """Measure lexical overlap as a diagnostic, not a semantic truth test."""

        terms = {
            token.casefold()
            for token in re.findall(r"\w+", question, flags=re.UNICODE)
            if len(token) >= 3
        }
        if not terms:
            return 1.0
        evidence_terms = {
            token.casefold()
            for candidate in candidates
            for token in re.findall(r"\w+", candidate.text, flags=re.UNICODE)
        }
        return len(terms & evidence_terms) / len(terms)
