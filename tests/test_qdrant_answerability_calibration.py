from labs.rag.chunking import ChunkSearchResult
from labs.rag.mentor_program_pdf_local_rag_eval import PdfRagEvaluationCase
from labs.rag.qdrant_answerability_calibration import evaluate_thresholds


class FakeRetriever:
    def search(self, query: str, top_k: int = 3) -> list[ChunkSearchResult]:
        score = 0.7 if query == "known" else 0.2
        return [ChunkSearchResult("chunk", "doc", "title", "text", "source", 0, score)]


def test_calibration_counts_false_positive_and_false_negative_by_threshold() -> None:
    cases = [
        PdfRagEvaluationCase("known", "answer", "known", []),
        PdfRagEvaluationCase("unknown", "no_answer", "unknown", []),
    ]

    report = evaluate_thresholds(cases, FakeRetriever(), [0.3, 0.8])

    assert report.case_count == 2
    assert report.evaluations[0].accuracy == 1.0
    assert report.evaluations[0].true_positive == 1
    assert report.evaluations[0].true_negative == 1
    assert report.evaluations[1].accuracy == 0.5
    assert report.evaluations[1].false_negative == 1
