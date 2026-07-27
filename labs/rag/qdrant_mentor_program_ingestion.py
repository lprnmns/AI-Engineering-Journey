from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from qdrant_client import QdrantClient

from labs.rag.chunking import chunk_documents
from labs.rag.dense_vectorizer import DenseVectorizer
from labs.rag.mentor_program_section_retrieval_experiment import (
    MENTOR_HEADER,
    MENTOR_SECTION_MARKERS,
)
from labs.rag.qdrant_vector_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_QDRANT_URL,
    QdrantVectorStore,
)
from labs.rag.structured_pdf_ingestion import pdf_to_section_documents


DEFAULT_PDF_PATH = Path("/home/alperen/Downloads/Alperen_Manas_Staj_Programi_1_Hafta 1.pdf")


def ingest_mentor_program_pdf(
    pdf_path: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    qdrant_url: str = DEFAULT_QDRANT_URL,
) -> dict[str, object]:
    documents = pdf_to_section_documents(
        pdf_path,
        markers=MENTOR_SECTION_MARKERS,
        repeated_prefix=MENTOR_HEADER,
    )
    chunks = chunk_documents(documents, sentences_per_chunk=2, overlap=1)
    store = QdrantVectorStore(
        collection_name=collection_name,
        client=QdrantClient(url=qdrant_url),
        vectorizer=DenseVectorizer(),
    )
    store.upsert_chunks(chunks)
    return {
        "pdf_filename": pdf_path.name,
        "section_count": len(documents),
        "chunk_count": len(chunks),
        "store": asdict(store.stats()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist section-aware mentor PDF chunks in Qdrant.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path. Parent directories are created when needed.",
    )
    args = parser.parse_args()

    report = ingest_mentor_program_pdf(args.pdf, args.collection, args.qdrant_url)
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{report_json}\n", encoding="utf-8")
    print(report_json)


if __name__ == "__main__":
    main()
