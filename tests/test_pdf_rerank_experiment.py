from pathlib import Path

import pytest

from labs.rag.chunking import ChunkSearchResult
from labs.rag import pdf_rerank_experiment
from labs.rag.reranker import RerankedChunkResult
from labs.rag.sample_docs import Document


class FakeReranker:
    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
        top_k: int = 3,
    ) -> list[RerankedChunkResult]:
        candidate = candidates[-1]
        return [
            RerankedChunkResult(
                chunk_id=candidate.chunk_id,
                doc_id=candidate.doc_id,
                title=candidate.title,
                text=candidate.text,
                source=candidate.source,
                chunk_index=candidate.chunk_index,
                retrieval_score=candidate.score,
                reranker_score=0.9,
            )
        ]


class FakeDenseVectorStore:
    def __init__(self, **_: object) -> None:
        self.chunks: list[object] = []

    def add_chunks(self, chunks: list[object]) -> None:
        self.chunks = chunks

    def search(self, query: str, top_k: int = 3) -> list[ChunkSearchResult]:
        return [
            ChunkSearchResult(
                chunk_id=f"chunk_{rank}",
                doc_id="mentor_program",
                title="Mentor Programı",
                text=f"{query} için aday {rank}",
                source="mentor.pdf",
                chunk_index=rank,
                score=1.0 - rank / 10,
            )
            for rank in range(1, top_k + 1)
        ]


def test_pdf_rerank_experiment_records_dense_candidates_and_reranked_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = Path("tests/fixtures/sample_document.pdf")
    monkeypatch.setattr(
        pdf_rerank_experiment,
        "pdf_to_document",
        lambda _: Document(
            doc_id="mentor_program",
            title="Mentor Programı",
            text="İlk cümle. İkinci cümle. Üçüncü cümle.",
            source="mentor.pdf",
        ),
    )
    monkeypatch.setattr(pdf_rerank_experiment, "DenseVectorStore", FakeDenseVectorStore)

    observations = pdf_rerank_experiment.run_pdf_rerank_experiment(
        pdf_path,
        dense_top_k=2,
        reranker=FakeReranker(),
    )

    assert len(observations) == 3
    assert all(len(observation.dense_candidates) == 2 for observation in observations)
    assert all(observation.reranker_score == 0.9 for observation in observations)
    assert all(observation.reranked_chunk_id == observation.dense_candidates[-1].chunk_id for observation in observations)
