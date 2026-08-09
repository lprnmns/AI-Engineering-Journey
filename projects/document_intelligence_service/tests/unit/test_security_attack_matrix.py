"""Regression tests for the declarative security attack matrix."""

from pathlib import Path

from projects.document_intelligence_service.eval.run_security_attack_matrix import (
    build_report,
    load_matrix,
)


MATRIX = Path("data/evaluations/security_attack_matrix_v1.json")


def test_security_attack_matrix_has_unique_controls_and_complete_evidence() -> None:
    matrix = load_matrix(MATRIX)
    report = build_report(matrix)

    assert report["summary"] == {
        "control_count": 8,
        "status_counts": {"not_ready": 1, "partial": 4, "pass": 3},
        "evidence_path_count": 27,
        "missing_evidence_path_count": 0,
        "missing_evidence_paths": [],
        "release_ready": False,
    }


def test_attack_matrix_keeps_acl_gap_explicit() -> None:
    matrix = load_matrix(MATRIX)

    acl_control = next(
        control for control in matrix["controls"] if control["id"] == "SEC-04"
    )

    assert acl_control["status"] == "not_ready"
    assert "501" in acl_control["observed_result"]
