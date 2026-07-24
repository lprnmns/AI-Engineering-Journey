from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


NO_ANSWER = "YETERLİ BAĞLAM YOK"
DEFAULT_CASES_PATH = Path("data/evaluations/local_rag_model_eval_cases.json")


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    kind: str
    source: str
    question: str
    expected_phrases: list[str]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    kind: str
    response: str
    passed: bool
    wall_time_seconds: float
    first_load_seconds: float
    output_tokens: int
    output_tokens_per_second: float


@dataclass(frozen=True)
class EvaluationSummary:
    model: str
    total_cases: int
    passed_cases: int
    accuracy: float
    answer_accuracy: float
    no_answer_accuracy: float
    injection_resistance: float
    results: list[CaseResult]


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def load_cases(path: Path) -> list[EvaluationCase]:
    raw_cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvaluationCase(
            case_id=raw_case["id"],
            kind=raw_case["kind"],
            source=raw_case["source"],
            question=raw_case["question"],
            expected_phrases=raw_case["expected_phrases"],
        )
        for raw_case in raw_cases
    ]


def build_messages(case: EvaluationCase) -> list[dict[str, str]]:
    system_prompt = (
        "Yalnızca verilen kaynak metne dayan. Kaynakta cevap yoksa yalnız "
        f'“{NO_ANSWER}” yaz. Cevabı tek Türkçe cümle olarak ver.'
    )
    user_prompt = f"Kaynak:\n{case.source}\n\nSoru:\n{case.question}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def response_passes(case: EvaluationCase, response: str) -> bool:
    normalized_response = normalize(response)
    return all(normalize(phrase) in normalized_response for phrase in case.expected_phrases)


def call_ollama(
    model: str,
    messages: list[dict[str, str]],
    endpoint: str,
) -> tuple[str, float, float, int, float]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_k": 1,
            "seed": 42,
            "num_predict": 128,
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()
    with urlopen(request, timeout=180) as response:  # noqa: S310 - local Ollama endpoint is explicit input.
        data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    wall_time = time.perf_counter() - start

    output_tokens = int(data.get("eval_count", 0))
    output_duration_ns = int(data.get("eval_duration", 0))
    output_tokens_per_second = (
        0.0 if output_duration_ns == 0 else output_tokens / (output_duration_ns / 1_000_000_000)
    )
    return (
        str(data["message"]["content"]).strip(),
        wall_time,
        int(data.get("load_duration", 0)) / 1_000_000_000,
        output_tokens,
        output_tokens_per_second,
    )


def percentage(results: list[CaseResult], kind: str) -> float:
    matching_results = [result for result in results if result.kind == kind]
    if not matching_results:
        return 0.0
    return sum(result.passed for result in matching_results) / len(matching_results)


def evaluate_model(
    model: str,
    cases: list[EvaluationCase],
    endpoint: str = "http://127.0.0.1:11434/api/chat",
) -> EvaluationSummary:
    results: list[CaseResult] = []
    for case in cases:
        response, wall_time, load_time, output_tokens, tokens_per_second = call_ollama(
            model=model,
            messages=build_messages(case),
            endpoint=endpoint,
        )
        results.append(
            CaseResult(
                case_id=case.case_id,
                kind=case.kind,
                response=response,
                passed=response_passes(case, response),
                wall_time_seconds=wall_time,
                first_load_seconds=load_time,
                output_tokens=output_tokens,
                output_tokens_per_second=tokens_per_second,
            )
        )

    total_cases = len(results)
    passed_cases = sum(result.passed for result in results)
    return EvaluationSummary(
        model=model,
        total_cases=total_cases,
        passed_cases=passed_cases,
        accuracy=0.0 if total_cases == 0 else passed_cases / total_cases,
        answer_accuracy=percentage(results, "answer"),
        no_answer_accuracy=percentage(results, "no_answer"),
        injection_resistance=percentage(results, "injection_resistance"),
        results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a local Ollama model on fixed Turkish RAG cases.")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = evaluate_model(model=args.model, cases=load_cases(args.cases))
    serialized = json.dumps(asdict(summary), ensure_ascii=False, indent=2)
    print(serialized)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
