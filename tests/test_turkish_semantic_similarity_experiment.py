from labs.embeddings.turkish_semantic_similarity_experiment import (
    PairCase,
    SentenceCase,
    evaluate_pairs,
)


class FakeVectorizer:
    model_name = "fake"

    def vectorize(self, text: str) -> list[float]:
        vectors = {
            "sol": [1.0, 0.0],
            "sağ": [0.0, 1.0],
        }
        return vectors[text]


def test_evaluate_pairs_reports_expected_cosine_score() -> None:
    report = evaluate_pairs(
        sentences=[
            SentenceCase("left", "sol"),
            SentenceCase("right", "sağ"),
        ],
        pairs=[PairCase("left", "right", "ilgisiz")],
        vectorizer=FakeVectorizer(),
    )

    assert report.model_name == "fake"
    assert report.sentence_count == 2
    assert report.embedding_dimension == 2
    assert report.pair_results[0].cosine_similarity == 0.0
