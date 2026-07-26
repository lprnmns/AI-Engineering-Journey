import pytest

from labs.model_eval.local_rag_model_eval import (
    EvaluationCase,
    build_messages,
    response_meets_style_target,
    response_passes,
)


def test_build_messages_keeps_source_and_question_separate() -> None:
    case = EvaluationCase(
        case_id="case",
        kind="answer",
        source="Kaynak bilgi.",
        question="Soru nedir?",
        expected_phrases=["bilgi"],
        style_target_phrases=["bilgi"],
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
        style_target_phrases=["almalısınız"],
    )

    assert response_passes(case, "Ekip yöneticisinin yazılı onayı gerekir.")
    assert not response_passes(case, "Ekip yöneticisinin onayı gerekir.")


def test_response_passes_ignores_case_and_terminal_punctuation() -> None:
    case = EvaluationCase("case", "no_answer", "", "", ["YETERLİ BAĞLAM YOK"], ["YETERLİ BAĞLAM YOK"])

    assert response_passes(case, "Yeterli bağlam yok.")


def test_build_messages_rejects_an_unknown_prompt_policy() -> None:
    case = EvaluationCase("case", "answer", "source", "question", ["source"], ["source"])

    with pytest.raises(KeyError):
        build_messages(case, prompt_policy="does_not_exist")


def test_response_meets_style_target_uses_a_separate_requirement() -> None:
    case = EvaluationCase("case", "answer", "", "", ["yazılı onay"], ["almalısınız"])

    assert not response_meets_style_target(case, "Ekip yöneticisinden yazılı onay.")
    assert response_meets_style_target(case, "Ekip yöneticinizin yazılı onayını almalısınız.")
