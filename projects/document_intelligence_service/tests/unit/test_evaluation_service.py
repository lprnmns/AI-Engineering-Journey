"""Tests for asynchronous evaluation lifecycle and raw artifacts."""

import asyncio
import json
from pathlib import Path

import pytest

from projects.document_intelligence_service.app.application.evaluation_service import (
    EvaluationExecution,
    EvaluationService,
    EvaluationSpec,
)
from projects.document_intelligence_service.app.domain.entities import (
    EvaluationRunStatus,
    RetrievalMode,
)
from projects.document_intelligence_service.app.domain.errors import (
    ErrorCode,
    ServiceError,
)
from projects.document_intelligence_service.app.infrastructure.storage.in_memory_evaluation_registry import (
    InMemoryEvaluationRegistry,
)


class FakeEvaluationExecutor:
    """Return deterministic metrics without loading Qdrant or a model."""

    def execute(self, spec: EvaluationSpec) -> EvaluationExecution:
        return EvaluationExecution(
            case_count=3,
            metrics={"recall_at_5": 1.0, "query_count": 3},
            raw={"strategy": spec.mode.value, "observations": []},
        )


def spec() -> EvaluationSpec:
    """Create one bounded test configuration."""

    return EvaluationSpec(
        evaluation_type="retrieval",
        dataset="mentor_program_pdf_rag_golden_v1",
        split="test",
        mode=RetrievalMode.HYBRID,
        top_k=5,
        reranker_enabled=False,
    )


def test_evaluation_run_persists_metrics_and_raw_artifact(tmp_path: Path) -> None:
    service = EvaluationService(
        registry=InMemoryEvaluationRegistry(),
        executor=FakeEvaluationExecutor(),
        artifact_dir=tmp_path / "artifacts",
        repo_root=tmp_path,
    )

    queued = asyncio.run(service.create_run(spec()))
    assert queued.status is EvaluationRunStatus.QUEUED
    completed = asyncio.run(service.execute_run(queued.run_id))

    assert completed.status is EvaluationRunStatus.SUCCEEDED
    assert completed.case_count == 3
    assert completed.metrics == {"recall_at_5": 1.0, "query_count": 3}
    assert completed.artifact_path is not None
    artifact = json.loads(Path(completed.artifact_path).read_text(encoding="utf-8"))
    assert artifact["run_id"] == queued.run_id
    assert artifact["metrics"]["recall_at_5"] == 1.0
    assert artifact["run"]["observations"] == []


def test_missing_evaluation_executor_fails_explicitly() -> None:
    service = EvaluationService(
        registry=InMemoryEvaluationRegistry(),
        executor=None,
        artifact_dir="/tmp/document-intelligence-eval-test",
        repo_root="/tmp",
    )

    queued = asyncio.run(service.create_run(spec()))
    failed = asyncio.run(service.execute_run(queued.run_id))

    assert failed.status is EvaluationRunStatus.FAILED
    assert failed.error_code == ErrorCode.DEPENDENCY_UNAVAILABLE.value
    with pytest.raises(ServiceError) as raised:
        asyncio.run(service.get_run("eval_missing"))
    assert raised.value.code is ErrorCode.EVALUATION_NOT_FOUND
