from __future__ import annotations

import argparse
from pathlib import Path

from labs.rag.mentor_program_pdf_local_rag_eval import DEFAULT_PDF_PATH
from labs.rag.mentor_program_section_retrieval_experiment import (
    MENTOR_HEADER,
    MENTOR_SECTION_MARKERS,
)
from labs.rag.qdrant_rag_pipeline import QdrantRagPipeline
from labs.rag.qdrant_vector_store import QdrantVectorStore
from labs.rag.structured_pdf_ingestion import pdf_to_section_documents


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show the Qdrant → reranker → context evidence path for one mentor PDF query."
    )
    parser.add_argument("query")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument("--candidate-top-k", type=int, default=5)
    parser.add_argument("--reranked-top-k", type=int, default=1)
    parser.add_argument(
        "--context-strategy",
        choices=["reranked_chunks", "parent_section"],
        default="parent_section",
    )
    parser.add_argument(
        "--min-dense-score",
        type=float,
        help="Optional evidence threshold. Set only after evaluation-based calibration.",
    )
    parser.add_argument("--max-context-characters", type=int, default=1_500)
    args = parser.parse_args()

    documents = pdf_to_section_documents(
        pdf_path=args.pdf,
        markers=MENTOR_SECTION_MARKERS,
        repeated_prefix=MENTOR_HEADER,
    )
    pipeline = QdrantRagPipeline.with_cross_encoder(QdrantVectorStore(), documents)
    output = pipeline.retrieve_and_build_context(
        args.query,
        candidate_top_k=args.candidate_top_k,
        reranked_top_k=args.reranked_top_k,
        context_strategy=args.context_strategy,
        min_dense_score=args.min_dense_score,
        max_context_characters=args.max_context_characters,
    )

    print(f"Answerable: {output.decision.is_answerable} ({output.decision.reason})")
    print("Dense candidates:")
    for dense_candidate in output.dense_candidates:
        print(
            f"- {dense_candidate.chunk_id} | {dense_candidate.doc_id} | "
            f"{dense_candidate.score:.3f}"
        )
    print("Reranked candidates:")
    for reranked_candidate in output.reranked_candidates:
        print(
            f"- {reranked_candidate.chunk_id} | {reranked_candidate.doc_id} | "
            f"dense={reranked_candidate.retrieval_score:.3f} | "
            f"reranker={reranked_candidate.reranker_score:.3f}"
        )
    print("Context:")
    print(output.context or "YETERLİ BAĞLAM YOK")


if __name__ == "__main__":
    main()
