from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from labs.rag.chunking import ChunkSearchResult, chunk_document
from labs.rag.dense_vector_store import DenseVectorStore
from labs.rag.dense_vectorizer import DenseVectorizer
from labs.rag.pdf_ingestion import pdf_to_document
from labs.rag.reranker import CrossEncoderReranker, RerankedChunkResult


DEFAULT_QUERIES = [
    "İlk haftanın amacı nedir?",
    "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
    "Teslim paketinde hangi çalışmalar bulunur?",
]


class CandidateReranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
        top_k: int = 3,
    ) -> list[RerankedChunkResult]: ...


@dataclass(frozen=True)
class CandidateObservation:
    rank: int
    chunk_id: str
    dense_score: float
    chunk_preview: str


@dataclass(frozen=True)
class RerankObservation:
    query: str
    dense_candidates: list[CandidateObservation]
    reranked_chunk_id: str
    reranked_dense_score: float
    reranker_score: float
    reranked_chunk_preview: str


def run_pdf_rerank_experiment(
    pdf_path: Path,
    *,
    dense_top_k: int = 5,
    reranker: CandidateReranker | None = None,
) -> list[RerankObservation]:
    """Compare dense top-k retrieval with cross-encoder reranking on one PDF."""
    document = pdf_to_document(pdf_path)
    chunks = chunk_document(document, sentences_per_chunk=2, overlap=1)
    store = DenseVectorStore(vectorizer=DenseVectorizer())
    store.add_chunks(chunks)
    active_reranker = reranker or CrossEncoderReranker()
    observations: list[RerankObservation] = []

    for query in DEFAULT_QUERIES:
        candidates = store.search(query, top_k=dense_top_k)
        reranked = active_reranker.rerank(query, candidates, top_k=1)
        if not reranked:
            raise RuntimeError("reranker returned no result for non-empty dense candidates")
        selected = reranked[0]
        observations.append(
            RerankObservation(
                query=query,
                dense_candidates=[
                    CandidateObservation(
                        rank=rank,
                        chunk_id=candidate.chunk_id,
                        dense_score=candidate.score,
                        chunk_preview=candidate.text[:240],
                    )
                    for rank, candidate in enumerate(candidates, start=1)
                ],
                reranked_chunk_id=selected.chunk_id,
                reranked_dense_score=selected.retrieval_score,
                reranker_score=selected.reranker_score,
                reranked_chunk_preview=selected.text[:240],
            )
        )
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description="Rerank dense PDF retrieval candidates with a cross-encoder.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    document = pdf_to_document(args.pdf)
    chunk_count = len(chunk_document(document, sentences_per_chunk=2, overlap=1))
    report = {
        "pdf_filename": args.pdf.name,
        "chunking": {
            "sentences_per_chunk": 2,
            "overlap": 1,
            "chunk_count": chunk_count,
        },
        "dense_retrieval": {"top_k": 5, "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"},
        "reranker": {"model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "top_k": 1},
        "results": [asdict(result) for result in run_pdf_rerank_experiment(args.pdf)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
