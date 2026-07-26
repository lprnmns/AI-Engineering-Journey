import pytest

from labs.model_eval.local_rag_model_eval import EvaluationCase
from labs.model_eval.repeat_local_rag_model_eval import evaluate_repeatedly


def test_evaluate_repeatedly_rejects_non_positive_run_count() -> None:
    case = EvaluationCase("case", "answer", "source", "question", ["source"])

    with pytest.raises(ValueError, match="runs must be greater than zero"):
        evaluate_repeatedly(
            model="unused",
            cases=[case],
            prompt_policy="v3_property_aware",
            runs=0,
        )
