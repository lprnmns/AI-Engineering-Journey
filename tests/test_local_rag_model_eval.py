from labs.model_eval.local_rag_model_eval import EvaluationCase, build_messages, response_passes


def test_build_messages_keeps_source_and_question_separate() -> None:
    case = EvaluationCase(
        case_id="case",
        kind="answer",
        source="Kaynak bilgi.",
        question="Soru nedir?",
        expected_phrases=["bilgi"],
    )

    messages = build_messages(case)

    assert messages[0]["role"] == "system"
    assert "YETERLİ BAĞLAM YOK" in messages[0]["content"]
    assert messages[1]["content"] == "Kaynak:\nKaynak bilgi.\n\nSoru:\nSoru nedir?"


def test_response_passes_requires_every_expected_phrase() -> None:
    case = EvaluationCase(
        case_id="case",
        kind="answer",
        source="",
        question="",
        expected_phrases=["ekip yöneticisinin", "yazılı onayı"],
    )

    assert response_passes(case, "Ekip yöneticisinin yazılı onayı gerekir.")
    assert not response_passes(case, "Ekip yöneticisinin onayı gerekir.")
