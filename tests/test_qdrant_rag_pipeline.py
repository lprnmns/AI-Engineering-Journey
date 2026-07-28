from labs.rag.chunking import ChunkSearchResult
from labs.rag.qdrant_rag_pipeline import QdrantRagPipeline
from labs.rag.reranker import RerankedChunkResult
from labs.rag.sample_docs import Document


def result(chunk_id: str, doc_id: str, score: float, text: str = "Dar kanıt.") -> ChunkSearchResult:
    return ChunkSearchResult(chunk_id, doc_id, doc_id, text, "mentor.pdf", 1, score)


class FakeRetriever:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self.results = results

    def search(self, query: str, top_k: int = 3) -> list[ChunkSearchResult]:
        return self.results[:top_k]


class FakeReranker:
    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
        top_k: int = 3,
    ) -> list[RerankedChunkResult]:
        chosen = candidates[-1]
        return [
            RerankedChunkResult(
                chunk_id=chosen.chunk_id,
                doc_id=chosen.doc_id,
                title=chosen.title,
                text=chosen.text,
                source=chosen.source,
                chunk_index=chosen.chunk_index,
                retrieval_score=chosen.score,
                reranker_score=0.9,
            )
        ]


def test_pipeline_reranks_then_expands_the_selected_parent_section() -> None:
    pipeline = QdrantRagPipeline(
        retriever=FakeRetriever(
            [result("wrong", "purpose", 0.7), result("right", "local_model", 0.5)]
        ),
        documents_by_id={
            "local_model": Document(
                "local_model", "Yerel model", "Tam bölümde bellek ölçümü var.", "mentor.pdf"
            )
        },
        reranker=FakeReranker(),
    )

    output = pipeline.retrieve_and_build_context("Ne ölçülür?", min_dense_score=0.4)

    assert output.decision.is_answerable
    assert output.reranked_candidates[0].chunk_id == "right"
    assert output.context_chunk_ids == ["local_model_parent_section"]
    assert "Tam bölümde bellek ölçümü var." in output.context


def test_pipeline_stops_before_reranking_when_evidence_is_below_policy_threshold() -> None:
    pipeline = QdrantRagPipeline(
        retriever=FakeRetriever([result("weak", "purpose", 0.2)]),
        documents_by_id={},
        reranker=FakeReranker(),
    )

    output = pipeline.retrieve_and_build_context("Maaş ne kadar?", min_dense_score=0.4)

    assert not output.decision.is_answerable
    assert output.decision.reason == "low_score"
    assert output.reranked_candidates == []
    assert output.context == ""
