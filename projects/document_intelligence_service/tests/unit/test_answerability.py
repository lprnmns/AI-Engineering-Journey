"""Unit tests for the pre-generation answerability policy."""

from projects.document_intelligence_service.app.domain.answerability import (
    AnswerabilityPolicy,
    AnswerabilitySignals,
)
from projects.document_intelligence_service.app.domain.entities import (
    Decision,
    NoAnswerReason,
)


def signals(
    *,
    evidence_count: int = 1,
    top_score: float | None = 0.8,
    score_margin: float | None = 0.2,
    coverage_ratio: float = 1.0,
    filters_satisfied: bool = True,
) -> AnswerabilitySignals:
    """Build one valid signal set with explicit test defaults."""

    return AnswerabilitySignals(
        evidence_count=evidence_count,
        top_score=top_score,
        score_margin=score_margin,
        coverage_ratio=coverage_ratio,
        filters_satisfied=filters_satisfied,
    )


def test_empty_evidence_is_no_answer_without_a_score() -> None:
    result = AnswerabilityPolicy().decide(
        signals=signals(evidence_count=0, top_score=None),
        score_kind="dense",
    )

    assert result.decision is Decision.NO_ANSWER
    assert result.reason is NoAnswerReason.NO_EVIDENCE


def test_low_dense_score_is_rejected_before_generation() -> None:
    result = AnswerabilityPolicy(min_dense_score=0.45).decide(
        signals=signals(top_score=0.12),
        score_kind="dense",
    )

    assert result.decision is Decision.NO_ANSWER
    assert result.reason is NoAnswerReason.LOW_RELEVANCE


def test_coverage_can_become_a_rejection_gate_when_calibrated() -> None:
    result = AnswerabilityPolicy(min_coverage=0.5).decide(
        signals=signals(coverage_ratio=0.2),
        score_kind="dense",
    )

    assert result.decision is Decision.NO_ANSWER
    assert result.reason is NoAnswerReason.INSUFFICIENT_COVERAGE


def test_relevant_evidence_is_answerable() -> None:
    result = AnswerabilityPolicy().decide(
        signals=signals(),
        score_kind="dense",
    )

    assert result.decision is Decision.ANSWERED
    assert result.reason is None
