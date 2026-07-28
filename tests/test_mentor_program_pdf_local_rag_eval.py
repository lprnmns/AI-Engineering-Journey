from pathlib import Path

from labs.rag.mentor_program_pdf_local_rag_eval import (
    PdfRagEvaluationCase,
    build_messages,
    evaluate_pdf_rag,
    response_passes,
)
from labs.rag.parent_section import parent_section_as_context_result
from labs.rag.reranker import RerankedChunkResult
from labs.rag.sample_docs import Document
from labs.model_eval.local_rag_model_eval import call_ollama
import pytest


def test_build_messages_keeps_context_separate_from_system_policy() -> None:
    messages = build_messages("Teslim paketi nedir?", "[1] Kaynak metin")

    assert messages[0]["role"] == "system"
    assert "YETERLİ BAĞLAM YOK" in messages[0]["content"]
    assert "Kaynak metin" not in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "[1] Kaynak metin" in messages[1]["content"]


def test_response_passes_requires_all_expected_phrases() -> None:
    case = PdfRagEvaluationCase(
        case_id="deliverables",
        kind="answer",
        question="Teslim paketi nedir?",
        expected_phrases=["model araştırma notu", "embedding deneyi"],
    )

    assert response_passes(case, "Model araştırma notu ve embedding deneyi bulunur.")
    assert not response_passes(case, "Yalnız model araştırma notu bulunur.")


def test_response_passes_handles_turkish_dotted_capital_i() -> None:
    case = PdfRagEvaluationCase(
        case_id="latency",
        kind="answer",
        question="Ne ölçülür?",
        expected_phrases=["ilk cevap süresi"],
    )

    assert response_passes(case, "İlk cevap süresi ölçülür.")


def test_call_ollama_rejects_non_positive_output_limit() -> None:
    with pytest.raises(ValueError, match="num_predict"):
        call_ollama("gemma3:4b", [], "http://127.0.0.1:11434/api/chat", num_predict=0)


def test_evaluate_pdf_rag_rejects_non_positive_reranked_top_k() -> None:
    with pytest.raises(ValueError, match="reranked_top_k"):
        evaluate_pdf_rag(
            pdf_path=Path("not-read.pdf"),
            cases=[],
            reranked_top_k=0,
        )


def test_evaluate_pdf_rag_rejects_non_positive_context_budget() -> None:
    with pytest.raises(ValueError, match="max_context_characters"):
        evaluate_pdf_rag(
            pdf_path=Path("not-read.pdf"),
            cases=[],
            max_context_characters=0,
        )


def test_evaluate_pdf_rag_rejects_unknown_retrieval_backend() -> None:
    with pytest.raises(ValueError, match="retrieval_backend"):
        evaluate_pdf_rag(
            pdf_path=Path("not-read.pdf"),
            cases=[],
            retrieval_backend="unknown",
        )


def test_parent_section_context_expands_selected_chunk_to_its_document() -> None:
    selected = RerankedChunkResult(
        chunk_id="local_model_chunk_006",
        doc_id="local_model",
        title="Yerel Model",
        text="Dar chunk.",
        source="mentor.pdf",
        chunk_index=6,
        retrieval_score=0.66,
        reranker_score=0.2,
    )
    documents = {
        "local_model": Document(
            doc_id="local_model",
            title="Yerel Model",
            text="Tam bölüm metni.",
            source="mentor.pdf",
        )
    }

    result = parent_section_as_context_result(selected, documents)

    assert result.chunk_id == "local_model_parent_section"
    assert result.text == "Tam bölüm metni."
    assert result.score == 0.66
