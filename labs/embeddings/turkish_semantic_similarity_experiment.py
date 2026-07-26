from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from labs.rag.dense_vectorizer import DEFAULT_MODEL_NAME, DenseVectorizer
from labs.rag.similarity import DenseVector, cosine_similarity

DEFAULT_CASES_PATH = Path("data/evaluations/turkish_embedding_similarity_cases.json")


class Vectorizer(Protocol):
    def vectorize(self, text: str) -> DenseVector: ...


@dataclass(frozen=True)
class SentenceCase:
    sentence_id: str
    text: str


@dataclass(frozen=True)
class PairCase:
    left_id: str
    right_id: str
    expectation: str


@dataclass(frozen=True)
class SearchQuery:
    query_id: str
    text: str
    expected_sentence_id: str


@dataclass(frozen=True)
class PairResult:
    left_id: str
    right_id: str
    left_text: str
    right_text: str
    expectation: str
    cosine_similarity: float


@dataclass(frozen=True)
class SearchResult:
    sentence_id: str
    text: str
    cosine_similarity: float


@dataclass(frozen=True)
class QueryRanking:
    query_id: str
    query_text: str
    expected_sentence_id: str
    ranked_results: list[SearchResult]


@dataclass(frozen=True)
class ExperimentReport:
    model_name: str
    sentence_count: int
    embedding_dimension: int
    pair_results: list[PairResult]
    query_rankings: list[QueryRanking]


def load_cases(path: Path) -> tuple[list[SentenceCase], list[PairCase], list[SearchQuery]]:
    raw: dict[str, list[dict[str, Any]]] = json.loads(path.read_text(encoding="utf-8"))
    sentences = [SentenceCase(sentence_id=item["id"], text=item["text"]) for item in raw["sentences"]]
    pairs = [
        PairCase(
            left_id=item["left_id"],
            right_id=item["right_id"],
            expectation=item["expectation"],
        )
        for item in raw["pairs"]
    ]
    queries = [
        SearchQuery(
            query_id=item["id"],
            text=item["text"],
            expected_sentence_id=item["expected_sentence_id"],
        )
        for item in raw["queries"]
    ]
    return sentences, pairs, queries


def evaluate_pairs(
    sentences: list[SentenceCase],
    pairs: list[PairCase],
    queries: list[SearchQuery],
    vectorizer: Vectorizer,
) -> ExperimentReport:
    text_by_id = {sentence.sentence_id: sentence.text for sentence in sentences}
    vectors_by_id = {
        sentence.sentence_id: vectorizer.vectorize(sentence.text)
        for sentence in sentences
    }
    results = [
        PairResult(
            left_id=pair.left_id,
            right_id=pair.right_id,
            left_text=text_by_id[pair.left_id],
            right_text=text_by_id[pair.right_id],
            expectation=pair.expectation,
            cosine_similarity=cosine_similarity(
                vectors_by_id[pair.left_id],
                vectors_by_id[pair.right_id],
            ),
        )
        for pair in pairs
    ]
    query_rankings = []
    for query in queries:
        query_vector = vectorizer.vectorize(query.text)
        ranked_results = sorted(
            (
                SearchResult(
                    sentence_id=sentence_id,
                    text=text_by_id[sentence_id],
                    cosine_similarity=cosine_similarity(query_vector, vector),
                )
                for sentence_id, vector in vectors_by_id.items()
            ),
            key=lambda item: item.cosine_similarity,
            reverse=True,
        )
        query_rankings.append(
            QueryRanking(
                query_id=query.query_id,
                query_text=query.text,
                expected_sentence_id=query.expected_sentence_id,
                ranked_results=ranked_results,
            )
        )
    dimension = len(next(iter(vectors_by_id.values()))) if vectors_by_id else 0
    return ExperimentReport(
        model_name=getattr(vectorizer, "model_name", DEFAULT_MODEL_NAME),
        sentence_count=len(sentences),
        embedding_dimension=dimension,
        pair_results=results,
        query_rankings=query_rankings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Turkish sentence embedding similarity experiment.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sentences, pairs, queries = load_cases(args.cases)
    report = evaluate_pairs(sentences, pairs, queries, DenseVectorizer())
    serialized = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    print(serialized)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
