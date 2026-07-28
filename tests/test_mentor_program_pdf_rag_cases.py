from pathlib import Path

from labs.rag.mentor_program_pdf_local_rag_eval import load_cases


V2_CASES_PATH = Path("data/evaluations/mentor_program_pdf_rag_cases_v2.json")


def test_expanded_mentor_pdf_cases_are_unique_and_cover_answers_and_rejections() -> None:
    cases = load_cases(V2_CASES_PATH)

    assert len(cases) == 18
    assert len({case.case_id for case in cases}) == len(cases)
    assert sum(case.kind == "answer" for case in cases) == 13
    assert sum(case.kind == "no_answer" for case in cases) == 3
    assert sum(case.kind == "injection_resistance" for case in cases) == 2
    assert all(case.expected_phrases for case in cases)
