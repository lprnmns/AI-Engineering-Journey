from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from labs.rag.chunking import chunk_documents
from labs.rag.dense_vector_store import DenseVectorStore
from labs.rag.dense_vectorizer import DenseVectorizer
from labs.rag.reranker import CrossEncoderReranker
from labs.rag.structured_pdf_ingestion import PdfSectionMarker, pdf_to_section_documents


MENTOR_HEADER = "BILGEADAM TEKNOLOJI | STAJYER GELİŞİM PROGRAMI Sayfa"
MENTOR_SECTION_MARKERS = [
    PdfSectionMarker("purpose", "Programın Amacı", "Programın Amacı"),
    PdfSectionMarker(
        "model_fundamentals",
        "01 Modelin nasıl düşündüğünü anla",
        "01 Modelin nasıl düşündüğünü anla",
    ),
    PdfSectionMarker(
        "embedding",
        "02 Embedding ve anlamsal aramayı somutlaştır",
        "02 Embedding ve anlamsal aramayı somutlaştır",
    ),
    PdfSectionMarker(
        "rag",
        "03 RAG akışının tamamını kur",
        "03 RAG akışının tamamını kur",
    ),
    PdfSectionMarker(
        "local_model",
        "04 Yerel modeli ayağa kaldır ve karşılaştır",
        "04 Yerel modeli ayağa kaldır ve karşılaştır",
    ),
    PdfSectionMarker(
        "corporate_problem",
        "05 Gerçek bir kurumsal problem seç",
        "05 Gerçek bir kurumsal problem seç",
    ),
    PdfSectionMarker("deliverables", "Teslim Paketi", "Teslim Paketi"),
]


@dataclass(frozen=True)
class SectionQuery:
    query: str
    expected_section_id: str


@dataclass(frozen=True)
class SectionRetrievalObservation:
    query: str
    expected_section_id: str
    dense_expected_rank: int | None
    dense_top_chunk_id: str
    dense_top_section_id: str
    dense_top_score: float
    reranked_chunk_id: str
    reranked_section_id: str
    reranker_score: float
    reranked_preview: str


DEFAULT_QUERIES = [
    SectionQuery("İlk haftanın amacı nedir?", "purpose"),
    SectionQuery(
        "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
        "local_model",
    ),
    SectionQuery("Teslim paketinde hangi çalışmalar bulunur?", "deliverables"),
]


def find_section_rank(section_ids: list[str], expected_section_id: str) -> int | None:
    for rank, section_id in enumerate(section_ids, start=1):
        if section_id == expected_section_id:
            return rank
    return None


def run_section_aware_experiment(pdf_path: Path) -> tuple[int, list[SectionRetrievalObservation]]:
    documents = pdf_to_section_documents(
        pdf_path,
        markers=MENTOR_SECTION_MARKERS,
        repeated_prefix=MENTOR_HEADER,
    )
    chunks = chunk_documents(documents, sentences_per_chunk=2, overlap=1)
    store = DenseVectorStore(vectorizer=DenseVectorizer())
    store.add_chunks(chunks)
    reranker = CrossEncoderReranker()
    observations: list[SectionRetrievalObservation] = []

    for item in DEFAULT_QUERIES:
        candidates = store.search(item.query, top_k=5)
        reranked = reranker.rerank(item.query, candidates, top_k=1)
        if not reranked:
            raise RuntimeError("reranker returned no result for non-empty dense candidates")
        selected = reranked[0]
        observations.append(
            SectionRetrievalObservation(
                query=item.query,
                expected_section_id=item.expected_section_id,
                dense_expected_rank=find_section_rank(
                    [candidate.doc_id for candidate in candidates],
                    item.expected_section_id,
                ),
                dense_top_chunk_id=candidates[0].chunk_id,
                dense_top_section_id=candidates[0].doc_id,
                dense_top_score=candidates[0].score,
                reranked_chunk_id=selected.chunk_id,
                reranked_section_id=selected.doc_id,
                reranker_score=selected.reranker_score,
                reranked_preview=selected.text[:240],
            )
        )
    return len(chunks), observations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate section-aware retrieval on the mentor program PDF."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    chunk_count, observations = run_section_aware_experiment(args.pdf)
    report = {
        "pdf_filename": args.pdf.name,
        "ingestion": {
            "strategy": "configured_section_markers_with_repeated_header_removal",
            "section_count": len(MENTOR_SECTION_MARKERS),
            "chunking": {"sentences_per_chunk": 2, "overlap": 1, "chunk_count": chunk_count},
        },
        "dense_retrieval": {
            "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "top_k": 5,
        },
        "reranker": {
            "model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            "top_k": 1,
        },
        "results": [asdict(observation) for observation in observations],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
