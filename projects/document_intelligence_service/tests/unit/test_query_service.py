"""Unit tests for retrieval, answerability and generation orchestration."""

import asyncio
from collections.abc import Sequence

from projects.document_intelligence_service.app.application.query_service import (
    QueryService,
)
from projects.document_intelligence_service.app.domain.answerability import (
    AnswerabilityPolicy,
)
from projects.document_intelligence_service.app.domain.entities import (
    Decision,
    NoAnswerReason,
    RetrievalMode,
)
from projects.document_intelligence_service.app.domain.generation import GeneratedAnswer
from projects.document_intelligence_service.app.domain.retrieval import RetrievedChunk
from projects.document_intelligence_service.tests.unit.test_retrieval_service import (
    make_service,
)


class FakeAnswerGenerator:
    """Return a deterministic answer and expose whether it was called."""

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self,
        *,
        question: str,
        evidence: Sequence[RetrievedChunk],
    ) -> GeneratedAnswer:
        del question
        self.call_count += 1
        assert evidence
        return GeneratedAnswer(
            answer="Kanıta dayalı test cevabı.",
            provider="fake",
            model="fake-model",
            latency_ms=4.0,
        )


def test_no_answer_skips_generator_and_returns_zero_llm_latency() -> None:
    async def scenario() -> None:
        generator = FakeAnswerGenerator()
        service = QueryService(
            retrieval_service=make_service(),
            answerability=AnswerabilityPolicy(min_dense_score=0.99),
            answer_generator=generator,
        )

        result = await service.execute(
            question="Stajyer maaşı ne kadar?",
            mode=RetrievalMode.HYBRID,
            top_k=3,
        )

        assert result.decision is Decision.NO_ANSWER
        assert result.no_answer_reason is NoAnswerReason.LOW_RELEVANCE
        assert result.answer is None
        assert result.sources == ()
        assert result.llm_ms == 0
        assert generator.call_count == 0

    asyncio.run(scenario())


def test_relevant_evidence_is_sent_to_generator() -> None:
    async def scenario() -> None:
        generator = FakeAnswerGenerator()
        service = QueryService(
            retrieval_service=make_service(),
            answerability=AnswerabilityPolicy(min_dense_score=0.45),
            answer_generator=generator,
        )

        result = await service.execute(
            question="Qdrant ne işe yarar?",
            mode=RetrievalMode.HYBRID,
            top_k=2,
        )

        assert result.decision is Decision.ANSWERED
        assert result.answer == "Kanıta dayalı test cevabı."
        assert result.no_answer_reason is None
        assert result.model == "fake-model"
        assert result.llm_ms == 4.0
        assert generator.call_count == 1

    asyncio.run(scenario())
