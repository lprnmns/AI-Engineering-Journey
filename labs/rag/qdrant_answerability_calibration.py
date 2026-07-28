from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from labs.rag.chunking import ChunkSearchResult
from labs.rag.mentor_program_pdf_local_rag_eval import (
    DEFAULT_CASES_PATH,
    PdfRagEvaluationCase,
    load_cases,
)
from labs.rag.qdrant_vector_store import QdrantVectorStore


class ScoreRetriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[ChunkSearchResult]: ...


@dataclass(frozen=True)
class ThresholdEvaluation:
    threshold: float
    accuracy: float
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int


@dataclass(frozen=True)
class QdrantAnswerabilityCalibration:
    case_count: int
    cases: list[dict[str, object]]
    evaluations: list[ThresholdEvaluation]


def evaluate_thresholds(
    cases: list[PdfRagEvaluationCase],
    retriever: ScoreRetriever,
    thresholds: list[float],
) -> QdrantAnswerabilityCalibration:
    if not thresholds:
        raise ValueError("thresholds must not be empty")
    if any(threshold < 0.0 for threshold in thresholds):
        raise ValueError("thresholds must be zero or greater")

    observed_cases: list[dict[str, object]] = []
    for case in cases:
        results = retriever.search(case.question, top_k=1)
        score = results[0].score if results else 0.0
        observed_cases.append(
            {
                "case_id": case.case_id,
                "kind": case.kind,
                "expected_answerable": case.kind == "answer",
                "top_chunk_id": results[0].chunk_id if results else None,
                "top_score": score,
            }
        )

    evaluations: list[ThresholdEvaluation] = []
    for threshold in thresholds:
        true_positive = true_negative = false_positive = false_negative = 0
        for observed_case in observed_cases:
            expected = bool(observed_case["expected_answerable"])
            top_score = observed_case["top_score"]
            if not isinstance(top_score, float):
                raise RuntimeError("observed top score must be a float")
            predicted = top_score >= threshold
            if expected and predicted:
                true_positive += 1
            elif not expected and not predicted:
                true_negative += 1
            elif not expected:
                false_positive += 1
            else:
                false_negative += 1
        total = len(observed_cases)
        evaluations.append(
            ThresholdEvaluation(
                threshold=threshold,
                accuracy=0.0 if total == 0 else (true_positive + true_negative) / total,
                true_positive=true_positive,
                true_negative=true_negative,
                false_positive=false_positive,
                false_negative=false_negative,
            )
        )

    return QdrantAnswerabilityCalibration(
        case_count=len(observed_cases),
        cases=observed_cases,
        evaluations=evaluations,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate a provisional Qdrant dense-score no-answer threshold."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--threshold", type=float, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    calibration = evaluate_thresholds(load_cases(args.cases), QdrantVectorStore(), args.threshold)
    serialized = json.dumps(asdict(calibration), ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
