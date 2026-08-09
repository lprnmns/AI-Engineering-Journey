"""Query orchestration: retrieve, gate, then optionally generate."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
import re
from time import perf_counter

from ..domain.answerability import (
    AnswerabilityDecision,
    AnswerabilityPolicy,
    AnswerabilitySignals,
)
from ..domain.entities import Decision, NoAnswerReason, RetrievalMode
from ..domain.errors import ErrorCode, ServiceError
from ..domain.evidence_safety import EvidenceSafetyPolicy
from ..domain.evidence_validation import (
    EvidenceWarning,
    validate_answer_against_evidence,
)
from ..domain.generation import AnswerGenerationError
from ..domain.prompt_safety import PromptSafetyPolicy
from ..domain.retrieval import RetrievedChunk, RetrievalResult
from ..observability.query_trace import (
    JsonQueryTraceSink,
    QueryTraceEvent,
    QueryTraceSink,
)
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
    warnings: tuple[EvidenceWarning, ...]


class QueryService:
    """Coordinate retrieval, pre-LLM rejection and grounded generation."""

    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        answerability: AnswerabilityPolicy,
        answer_generator: AnswerGenerator,
        prompt_safety: PromptSafetyPolicy | None = None,
        evidence_safety: EvidenceSafetyPolicy | None = None,
        trace_sink: QueryTraceSink | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._answerability = answerability
        self._answer_generator = answer_generator
        self._prompt_safety = prompt_safety or PromptSafetyPolicy()
        self._evidence_safety = evidence_safety or EvidenceSafetyPolicy()
        self._trace_sink = trace_sink or JsonQueryTraceSink()

    async def execute(
        self,
        *,
        question: str,
        mode: RetrievalMode,
        top_k: int,
        document_ids: Sequence[str] = (),
        tenant_id: str = "default",
        acl_tags: Sequence[str] = ("public",),
    ) -> QueryExecutionResult:
        """Run the bounded query sequence and skip generation when unsafe."""

        started = perf_counter()
        if self._prompt_safety.evaluate(question).blocked:
            retrieval = _empty_retrieval(mode)
            gate = assess_answerability(
                question=question,
                retrieval=retrieval,
                answerability=self._answerability,
                prompt_safety=self._prompt_safety,
            )
            return self._record_and_return(
                question,
                QueryExecutionResult(
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
                    warnings=(),
                ),
            )
        retrieval = await asyncio.to_thread(
            self._retrieval_service.search,
            question=question,
            mode=mode,
            top_k=top_k,
            document_ids=document_ids,
            tenant_id=tenant_id,
            acl_tags=acl_tags,
        )
        retrieval, blocked_evidence = _apply_evidence_safety(
            retrieval,
            policy=self._evidence_safety,
        )
        gate = assess_answerability(
            question=question,
            retrieval=retrieval,
            answerability=self._answerability,
            prompt_safety=self._prompt_safety,
            evidence_safety_blocked=blocked_evidence and not retrieval.candidates,
        )
        if gate.decision is Decision.NO_ANSWER:
            return self._record_and_return(
                question,
                QueryExecutionResult(
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
                    warnings=(),
                ),
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
        validation = validate_answer_against_evidence(
            answer=generated.answer,
            evidence=retrieval.candidates,
        )
        return self._record_and_return(
            question,
            QueryExecutionResult(
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
                warnings=validation.warnings,
            ),
        )

    def _record_and_return(
        self,
        question: str,
        result: QueryExecutionResult,
    ) -> QueryExecutionResult:
        """Record a privacy-safe trace before returning an application result."""

        self._trace_sink.record(
            QueryTraceEvent.from_query_result(
                question=question,
                decision=result.decision,
                no_answer_reason=result.no_answer_reason,
                retrieval=result.retrieval,
                selected_evidence_count=len(result.sources),
                top_score=result.answerability.top_score,
                score_margin=result.answerability.score_margin,
                coverage_ratio=result.answerability.coverage_ratio,
                provider=result.provider,
                model=result.model,
                warnings=result.warnings,
                llm_ms=result.llm_ms,
                total_ms=result.total_ms,
            )
        )
        return result

    def _signals(
        self,
        question: str,
        retrieval: RetrievalResult,
    ) -> tuple[AnswerabilitySignals, str]:
        """Extract comparable score and coverage signals from retrieval trace."""

        return build_answerability_signals(question, retrieval)

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
            for token in re.findall(r"\w+", candidate.context_text, flags=re.UNICODE)
        }
        return len(terms & evidence_terms) / len(terms)


def assess_answerability(
    *,
    question: str,
    retrieval: RetrievalResult,
    answerability: AnswerabilityPolicy,
    prompt_safety: PromptSafetyPolicy | None = None,
    evidence_safety_blocked: bool = False,
) -> AnswerabilityDecision:
    """Apply the pre-LLM gate to a previously captured retrieval result."""

    safety = prompt_safety or PromptSafetyPolicy()
    if safety.evaluate(question).blocked:
        return AnswerabilityDecision(
            decision=Decision.NO_ANSWER,
            reason=NoAnswerReason.SECURITY_POLICY,
            top_score=None,
            score_margin=None,
            coverage_ratio=0.0,
        )
    if evidence_safety_blocked:
        return AnswerabilityDecision(
            decision=Decision.NO_ANSWER,
            reason=NoAnswerReason.SECURITY_POLICY,
            top_score=None,
            score_margin=None,
            coverage_ratio=0.0,
        )
    signals, score_kind = build_answerability_signals(question, retrieval)
    return answerability.decide(signals=signals, score_kind=score_kind)


def build_answerability_signals(
    question: str,
    retrieval: RetrievalResult,
) -> tuple[AnswerabilitySignals, str]:
    """Build the same trace signals used by the live query path."""

    score_kind = QueryService._score_kind(retrieval)
    scores = tuple(
        QueryService._score_for(candidate, score_kind)
        for candidate in retrieval.candidates
    )
    # Hybrid candidates are ordered by RRF, not by the score used by the
    # answerability policy. Sort the comparable score values before deriving
    # top-score and margin; otherwise a valid dense result can look like a
    # negative-margin near miss merely because sparse ranking placed first.
    ranked_scores = tuple(sorted(scores, reverse=True))
    top_score = ranked_scores[0] if ranked_scores else None
    margin = (
        ranked_scores[0] - ranked_scores[1]
        if len(ranked_scores) > 1
        else None
    )
    return (
        AnswerabilitySignals(
            evidence_count=len(retrieval.candidates),
            top_score=top_score,
            score_margin=margin,
            coverage_ratio=QueryService._coverage_ratio(
                question,
                retrieval.candidates,
            ),
        ),
        score_kind,
    )


def _empty_retrieval(mode: RetrievalMode) -> RetrievalResult:
    """Create a zero-cost trace for a query blocked before retrieval."""

    return RetrievalResult(
        mode=mode.value,
        candidates=(),
        dense_candidates=0,
        sparse_candidates=0,
        rrf_candidates=0,
        embedding_ms=0.0,
        search_ms=0.0,
    )


def _apply_evidence_safety(
    retrieval: RetrievalResult,
    *,
    policy: EvidenceSafetyPolicy,
) -> tuple[RetrievalResult, bool]:
    """Filter unsafe final/context candidates before answerability or LLM."""

    final_result = policy.filter(retrieval.candidates)
    window = retrieval.candidate_window or retrieval.candidates
    window_result = policy.filter(window)
    blocked = bool(
        final_result.blocked_source_ids or window_result.blocked_source_ids
    )
    if not blocked:
        return retrieval, False

    safe_final_ids = {item.source_id for item in final_result.safe_evidence}
    safe_window_ids = {item.source_id for item in window_result.safe_evidence}
    return (
        replace(
            retrieval,
            candidates=tuple(
                item
                for item in retrieval.candidates
                if item.source_id in safe_final_ids
            ),
            candidate_window=tuple(
                item for item in window if item.source_id in safe_window_ids
            ),
        ),
        True,
    )
