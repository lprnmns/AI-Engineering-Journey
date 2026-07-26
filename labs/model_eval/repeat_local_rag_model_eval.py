from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from labs.model_eval.local_rag_model_eval import (
    DEFAULT_CASES_PATH,
    PROMPT_POLICIES,
    EvaluationCase,
    EvaluationSummary,
    evaluate_model,
    load_cases,
)


@dataclass(frozen=True)
class RepeatedEvaluationSummary:
    model: str
    prompt_policy: str
    runs: int
    mean_accuracy: float
    minimum_accuracy: float
    maximum_accuracy: float
    case_pass_rates: dict[str, float]
    run_summaries: list[EvaluationSummary]


def evaluate_repeatedly(
    model: str,
    cases: list[EvaluationCase],
    prompt_policy: str,
    runs: int,
) -> RepeatedEvaluationSummary:
    if runs <= 0:
        raise ValueError("runs must be greater than zero")

    run_summaries = [
        evaluate_model(model=model, cases=cases, prompt_policy=prompt_policy)
        for _ in range(runs)
    ]
    accuracies = [summary.accuracy for summary in run_summaries]
    case_pass_rates = {
        case.case_id: sum(
            result.passed
            for summary in run_summaries
            for result in summary.results
            if result.case_id == case.case_id
        )
        / runs
        for case in cases
    }
    return RepeatedEvaluationSummary(
        model=model,
        prompt_policy=prompt_policy,
        runs=runs,
        mean_accuracy=sum(accuracies) / runs,
        minimum_accuracy=min(accuracies),
        maximum_accuracy=max(accuracies),
        case_pass_rates=case_pass_rates,
        run_summaries=run_summaries,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeat fixed local RAG model evaluation runs.")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--prompt-policy", choices=sorted(PROMPT_POLICIES), required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = evaluate_repeatedly(
        model=args.model,
        cases=load_cases(args.cases),
        prompt_policy=args.prompt_policy,
        runs=args.runs,
    )
    serialized = json.dumps(asdict(summary), ensure_ascii=False, indent=2)
    print(serialized)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
