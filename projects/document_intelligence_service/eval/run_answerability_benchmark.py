"""Run the live answerability gate without calling Ollama."""

from argparse import ArgumentParser
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from ..app.domain.answerability import AnswerabilityPolicy
from ..app.domain.entities import RetrievalMode
from ..app.domain.ingestion import PipelineConfig
from ..app.main import build_retrieval_service
from ..app.settings import Settings
from .contracts import load_jsonl, validate_case_set
from .runner import run_answerability_benchmark

DEFAULT_DATASET = Path("data/evaluations/mentor_program_pdf_rag_golden_v1.jsonl")
DEFAULT_WARMUPS = (
    "Qdrant ne işe yarar?",
    "Embedding ne demektir?",
    "RAG akışı hangi adımlardan oluşur?",
)


def main() -> None:
    """Run the gate on all cases and persist its raw decisions."""

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dense", "bm25", "hybrid"), default="hybrid")
    parser.add_argument("--reranker", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = validate_case_set(
        load_jsonl(args.dataset),
        minimum_count=44,
        expected_category_counts={
            "direct_fact": 8,
            "paraphrase": 6,
            "exact_term": 6,
            "near_miss": 6,
            "no_answer": 6,
            "multi_evidence": 4,
            "prompt_injection": 4,
            "leakage_acl": 4,
        },
    )
    settings = Settings(
        section_marker_profile="mentor_program_v1",
        reranker_enabled=args.reranker,
    )
    service = build_retrieval_service(settings)
    policy = AnswerabilityPolicy(
        min_dense_score=settings.answerability_min_dense_score,
        min_sparse_score=settings.answerability_min_sparse_score,
        min_rerank_score=settings.answerability_min_rerank_score,
        min_margin=settings.answerability_min_margin,
        min_coverage=settings.answerability_min_coverage,
    )
    run = run_answerability_benchmark(
        retrieval_service=service,
        answerability=policy,
        cases=cases,
        mode=RetrievalMode(args.mode),
        top_k=args.top_k,
        warmup_questions=DEFAULT_WARMUPS,
    )
    report = {
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "dataset": str(args.dataset),
        "mode": args.mode,
        "reranker_enabled": args.reranker,
        "top_k": args.top_k,
        "warmup_questions": list(DEFAULT_WARMUPS),
        "llm_called": False,
        "answerability_policy": {
            "min_dense_score": policy.min_dense_score,
            "min_sparse_score": policy.min_sparse_score,
            "min_rerank_score": policy.min_rerank_score,
            "min_margin": policy.min_margin,
            "min_coverage": policy.min_coverage,
        },
        "qdrant_collection": "document_chunks_v2_bm25",
        "sparse_encoder": PipelineConfig().sparse_encoder,
        "run": asdict(run),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metrics = run.metrics
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cases": run.cases_run,
                "false_positive_no_answer": metrics.no_answer_false_positive_count,
                "false_negative_no_answer": metrics.no_answer_false_negative_count,
                "false_positive_rate": metrics.no_answer_false_positive_rate,
                "false_negative_rate": metrics.no_answer_false_negative_rate,
                "total_p50_ms": run.total_latency.p50_ms,
                "total_p95_ms": run.total_latency.p95_ms,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
