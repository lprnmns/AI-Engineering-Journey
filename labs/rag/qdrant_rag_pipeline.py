from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from labs.rag.chunking import ChunkSearchResult
from labs.rag.context_builder import build_context
from labs.rag.no_answer_detection import RetrievalDecision, decide_answerability
from labs.rag.parent_section import parent_section_as_context_result
from labs.rag.reranker import CrossEncoderReranker, RerankedChunkResult
from labs.rag.sample_docs import Document


class ChunkRetriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[ChunkSearchResult]: ...


class CandidateReranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
        top_k: int = 3,
    ) -> list[RerankedChunkResult]: ...


@dataclass(frozen=True)
class QdrantRagPipelineResult:
    query: str
    decision: RetrievalDecision
    dense_candidates: list[ChunkSearchResult]
    reranked_candidates: list[RerankedChunkResult]
    context: str
    context_chunk_ids: list[str]
    context_section_ids: list[str]


@dataclass
class QdrantRagPipeline:
    """Make retrieval evidence explicit before sending it to a local LLM.

    This class deliberately stops at context construction. Generation stays in the
    local-model layer, so retrieval can be tested without a running Ollama model.
    """

    retriever: ChunkRetriever
    documents_by_id: dict[str, Document]
    reranker: CandidateReranker

    @classmethod
    def with_cross_encoder(
        cls,
        retriever: ChunkRetriever,
        documents: list[Document],
    ) -> QdrantRagPipeline:
        return cls(
            retriever=retriever,
            documents_by_id={document.doc_id: document for document in documents},
            reranker=CrossEncoderReranker(),
        )

    def retrieve_and_build_context(
        self,
        query: str,
        candidate_top_k: int = 5,
        reranked_top_k: int = 1,
        context_strategy: str = "parent_section",
        min_dense_score: float | None = None,
        min_dense_margin: float = 0.0,
        max_context_characters: int | None = None,
    ) -> QdrantRagPipelineResult:
        if candidate_top_k <= 0:
            raise ValueError("candidate_top_k must be greater than zero")
        if reranked_top_k <= 0:
            raise ValueError("reranked_top_k must be greater than zero")
        if context_strategy not in {"reranked_chunks", "parent_section"}:
            raise ValueError("context_strategy must be reranked_chunks or parent_section")
        if min_dense_score is not None and min_dense_score < 0.0:
            raise ValueError("min_dense_score must be zero or greater")

        dense_candidates = self.retriever.search(query, top_k=candidate_top_k)
        decision = decide_answerability(
            query,
            dense_candidates,
            min_score=0.0 if min_dense_score is None else min_dense_score,
            min_margin=min_dense_margin,
        )
        if not decision.is_answerable:
            return QdrantRagPipelineResult(
                query=query,
                decision=decision,
                dense_candidates=dense_candidates,
                reranked_candidates=[],
                context="",
                context_chunk_ids=[],
                context_section_ids=[],
            )

        reranked_candidates = self.reranker.rerank(
            query,
            dense_candidates,
            top_k=reranked_top_k,
        )
        if not reranked_candidates:
            raise RuntimeError("reranker returned no result for non-empty dense candidates")

        if context_strategy == "parent_section":
            context_results = [
                parent_section_as_context_result(reranked_candidates[0], self.documents_by_id)
            ]
        else:
            context_results = [
                ChunkSearchResult(
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    title=result.title,
                    text=result.text,
                    source=result.source,
                    chunk_index=result.chunk_index,
                    score=result.retrieval_score,
                )
                for result in reranked_candidates
            ]

        return QdrantRagPipelineResult(
            query=query,
            decision=decision,
            dense_candidates=dense_candidates,
            reranked_candidates=reranked_candidates,
            context=build_context(context_results, max_chars=max_context_characters),
            context_chunk_ids=[result.chunk_id for result in context_results],
            context_section_ids=[result.doc_id for result in context_results],
        )
