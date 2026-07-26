from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from labs.rag.chunking import chunk_document
from labs.rag.dense_vector_store import DenseVectorStore
from labs.rag.dense_vectorizer import DenseVectorizer
from labs.rag.pdf_ingestion import pdf_to_document


@dataclass(frozen=True)
class ChunkConfiguration:
    name: str
    sentences_per_chunk: int
    overlap: int


@dataclass(frozen=True)
class SearchObservation:
    query: str
    chunk_id: str
    score: float
    chunk_characters: int
    chunk_preview: str


@dataclass(frozen=True)
class ChunkExperimentResult:
    configuration: ChunkConfiguration
    chunk_count: int
    average_chunk_characters: float
    searches: list[SearchObservation]


DEFAULT_CONFIGURATIONS = [
    ChunkConfiguration("small_2_sentences_overlap_1", sentences_per_chunk=2, overlap=1),
    ChunkConfiguration("large_5_sentences_overlap_1", sentences_per_chunk=5, overlap=1),
]

DEFAULT_QUERIES = [
    "İlk haftanın amacı nedir?",
    "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
    "Teslim paketinde hangi çalışmalar bulunur?",
]


def run_chunk_experiment(pdf_path: Path) -> list[ChunkExperimentResult]:
    document = pdf_to_document(pdf_path)
    vectorizer = DenseVectorizer()
    results: list[ChunkExperimentResult] = []

    for configuration in DEFAULT_CONFIGURATIONS:
        chunks = chunk_document(
            document,
            sentences_per_chunk=configuration.sentences_per_chunk,
            overlap=configuration.overlap,
        )
        store = DenseVectorStore(vectorizer=vectorizer)
        store.add_chunks(chunks)
        searches = []
        for query in DEFAULT_QUERIES:
            top_result = store.search(query, top_k=1)[0]
            searches.append(
                SearchObservation(
                    query=query,
                    chunk_id=top_result.chunk_id,
                    score=top_result.score,
                    chunk_characters=len(top_result.text),
                    chunk_preview=top_result.text[:240],
                )
            )
        results.append(
            ChunkExperimentResult(
                configuration=configuration,
                chunk_count=len(chunks),
                average_chunk_characters=sum(len(chunk.text) for chunk in chunks) / len(chunks),
                searches=searches,
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two sentence chunking configurations on a PDF.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = {
        "pdf_filename": args.pdf.name,
        "results": [asdict(result) for result in run_chunk_experiment(args.pdf)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
