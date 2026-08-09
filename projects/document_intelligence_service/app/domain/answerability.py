"""Framework-independent answerability policy and decision signals."""

from dataclasses import dataclass

from .entities import Decision, NoAnswerReason


@dataclass(frozen=True, slots=True)
class AnswerabilitySignals:
    """Evidence signals evaluated before an LLM is allowed to run."""

    evidence_count: int
    top_score: float | None
    score_margin: float | None
    coverage_ratio: float
    filters_satisfied: bool = True

    def __post_init__(self) -> None:
        if self.evidence_count < 0:
            raise ValueError("evidence_count must not be negative")
        if self.coverage_ratio < 0 or self.coverage_ratio > 1:
            raise ValueError("coverage_ratio must be between zero and one")


@dataclass(frozen=True, slots=True)
class AnswerabilityDecision:
    """Stable result of the pre-generation answerability gate."""

    decision: Decision
    reason: NoAnswerReason | None
    top_score: float | None
    score_margin: float | None
    coverage_ratio: float


@dataclass(frozen=True, slots=True)
class AnswerabilityPolicy:
    """Apply provisional, explicitly configurable evidence thresholds.

    The thresholds are calibration inputs, not universal truths. They must be
    re-estimated on a golden validation split before a production rollout.
    ``min_margin`` and ``min_coverage`` default to zero because this first
    vertical slice records those signals before enough labeled data exists to
    turn them into safe rejection gates.
    """

    min_dense_score: float = 0.456
    min_sparse_score: float = 0.1
    min_rerank_score: float = -5.0
    min_margin: float = 0.0
    min_coverage: float = 0.0

    def __post_init__(self) -> None:
        if self.min_coverage < 0 or self.min_coverage > 1:
            raise ValueError("min_coverage must be between zero and one")

    def decide(
        self,
        *,
        signals: AnswerabilitySignals,
        score_kind: str,
    ) -> AnswerabilityDecision:
        """Return answered/no-answer without consulting an LLM."""

        if signals.evidence_count == 0 or signals.top_score is None:
            return self._no_answer(signals, NoAnswerReason.NO_EVIDENCE)
        if not signals.filters_satisfied:
            return self._no_answer(signals, NoAnswerReason.INSUFFICIENT_COVERAGE)

        minimum = self._minimum_for(score_kind)
        if signals.top_score < minimum:
            return self._no_answer(signals, NoAnswerReason.LOW_RELEVANCE)
        if signals.coverage_ratio < self.min_coverage:
            return self._no_answer(
                signals,
                NoAnswerReason.INSUFFICIENT_COVERAGE,
            )
        if (
            signals.score_margin is not None
            and signals.score_margin < self.min_margin
        ):
            return self._no_answer(signals, NoAnswerReason.LOW_RELEVANCE)
        return AnswerabilityDecision(
            decision=Decision.ANSWERED,
            reason=None,
            top_score=signals.top_score,
            score_margin=signals.score_margin,
            coverage_ratio=signals.coverage_ratio,
        )

    def _minimum_for(self, score_kind: str) -> float:
        if score_kind == "rerank":
            return self.min_rerank_score
        if score_kind == "sparse":
            return self.min_sparse_score
        return self.min_dense_score

    @staticmethod
    def _no_answer(
        signals: AnswerabilitySignals,
        reason: NoAnswerReason,
    ) -> AnswerabilityDecision:
        return AnswerabilityDecision(
            decision=Decision.NO_ANSWER,
            reason=reason,
            top_score=signals.top_score,
            score_margin=signals.score_margin,
            coverage_ratio=signals.coverage_ratio,
        )
