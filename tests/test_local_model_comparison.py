from labs.model_eval.local_model_comparison import (
    ComparisonCase,
    ModelSpec,
    evaluate_model,
    response_passes,
)


def test_response_passes_requires_all_expected_phrases() -> None:
    case = ComparisonCase("code", "code_generation", "prompt", ["def", "return"], [])

    assert response_passes(case, "def clean():\n    return []")
    assert not response_passes(case, "def clean():\n    pass")


def test_response_passes_accepts_one_phrase_from_each_alternative_group() -> None:
    case = ComparisonCase("rag", "turkish_technical", "prompt", [], [["aday", "sonuç"], ["sıral"]])

    assert response_passes(case, "Sonuçları daha ilgili olana göre sıralar.")
    assert not response_passes(case, "Sonuçları getirir.")


def test_evaluate_model_aggregates_fixed_case_metrics_without_a_real_model() -> None:
    cases = [
        ComparisonCase("one", "logic", "one", ["kanıt"], []),
        ComparisonCase("two", "summary", "two", ["özet"], []),
    ]
    calls: list[str] = []

    def fake_call_model(**kwargs: object) -> tuple[str, float, float, int, float]:
        calls.append(str(kwargs["model"]))
        return ("kanıt ve özet", 2.0, 0.5, 4, 2.0)

    result = evaluate_model(
        ModelSpec("fake", "Fake", "test", 1.0, "test"),
        cases,
        call_model=fake_call_model,
        memory_reader=lambda: 512.0,
        cold_start=False,
        unload_after=False,
    )

    assert calls == ["fake", "fake"]
    assert result.passed_cases == 2
    assert result.accuracy == 1.0
    assert result.first_response_wall_time_seconds == 2.0
    assert result.total_wall_time_seconds == 4.0
    assert result.peak_ollama_container_memory_mib == 512.0
