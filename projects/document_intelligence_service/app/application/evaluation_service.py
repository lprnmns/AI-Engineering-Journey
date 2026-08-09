"""Asynchronous, reproducible evaluation orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Protocol, cast
from uuid import uuid4

from ..domain.answerability import AnswerabilityPolicy
from ..domain.entities import EvaluationRunStatus, RetrievalMode
from ..domain.errors import ErrorCode, ServiceError
from ..domain.evaluation import EvaluationRunSnapshot, MetricValue
from .ports import EvaluationRegistry


@dataclass(frozen=True, slots=True)
class EvaluationSpec:
    """Validated options shared by API requests and offline runners."""

    evaluation_type: str
    dataset: str
    split: str
    mode: RetrievalMode
    top_k: int
    reranker_enabled: bool


@dataclass(frozen=True, slots=True)
class EvaluationExecution:
    """Serializable output produced by one evaluation executor."""

    case_count: int
    metrics: dict[str, MetricValue]
    raw: dict[str, object]


class EvaluationExecutor(Protocol):
    """Port for the expensive benchmark implementation."""

    def execute(self, spec: EvaluationSpec) -> EvaluationExecution:
        """Run a bounded benchmark without an HTTP request context."""

        ...


class OfflineEvaluationExecutor:
    """Adapter around the repository's existing golden-set runners."""

    _DATASETS = {
        "mentor_program_pdf_rag_golden_v1": "data/evaluations/mentor_program_pdf_rag_golden_v1.jsonl",
    }

    def __init__(
        self,
        *,
        retrieval_service: object | None,
        answerability: AnswerabilityPolicy,
        repo_root: Path,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._answerability = answerability
        self._repo_root = repo_root

    def execute(self, spec: EvaluationSpec) -> EvaluationExecution:
        """Load an allow-listed golden set and run the selected metric suite."""

        if self._retrieval_service is None:
            raise ServiceError(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message="Retrieval service is unavailable for evaluation",
            )
        if spec.evaluation_type not in {"retrieval", "answerability"}:
            raise ServiceError(
                code=ErrorCode.INVALID_REQUEST,
                message="Unsupported evaluation type",
            )
        dataset_relative = self._DATASETS.get(spec.dataset)
        if dataset_relative is None:
            raise ServiceError(
                code=ErrorCode.INVALID_REQUEST,
                message="Dataset is not allow-listed",
            )
        dataset = self._repo_root / dataset_relative
        if not dataset.is_file():
            raise ServiceError(
                code=ErrorCode.EVALUATION_FAILED,
                message="Evaluation dataset is missing",
            )

        from ...eval.contracts import load_jsonl, validate_case_set

        cases = validate_case_set(load_jsonl(dataset), minimum_count=1)
        if spec.split != "all":
            cases = tuple(case for case in cases if case.split == spec.split)
        if not cases:
            raise ServiceError(
                code=ErrorCode.INVALID_REQUEST,
                message="Evaluation split contains no cases",
            )

        from ...eval.runner import (
            AnswerabilityBenchmarkRun,
            RetrievalPort,
            RetrievalBenchmarkRun,
            run_answerability_benchmark,
            run_retrieval_benchmark,
        )

        retrieval_service = cast(RetrievalPort, self._retrieval_service)
        run: RetrievalBenchmarkRun | AnswerabilityBenchmarkRun
        if spec.evaluation_type == "retrieval":
            run = run_retrieval_benchmark(
                retrieval_service=retrieval_service,
                cases=cases,
                mode=spec.mode,
                top_k=spec.top_k,
            )
        else:
            run = run_answerability_benchmark(
                retrieval_service=retrieval_service,
                answerability=self._answerability,
                cases=cases,
                mode=spec.mode,
                top_k=spec.top_k,
            )
        raw = cast(dict[str, object], asdict(run))
        metrics = _scalar_metrics(cast(dict[str, object], asdict(run.metrics)))
        return EvaluationExecution(
            case_count=len(cases),
            metrics=metrics,
            raw=raw,
        )


class EvaluationService:
    """Create, execute and expose evaluation runs without fabricating results."""

    def __init__(
        self,
        *,
        registry: EvaluationRegistry,
        executor: EvaluationExecutor | None,
        artifact_dir: str | Path,
        repo_root: str | Path,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._artifact_dir = Path(artifact_dir)
        self._repo_root = Path(repo_root)

    async def create_run(self, spec: EvaluationSpec) -> EvaluationRunSnapshot:
        """Queue one run and return its stable identifier immediately."""

        run = EvaluationRunSnapshot(
            run_id=f"eval_{uuid4().hex}",
            status=EvaluationRunStatus.QUEUED,
            evaluation_type=spec.evaluation_type,
            dataset=spec.dataset,
            split=spec.split,
            mode=spec.mode,
            top_k=spec.top_k,
            reranker_enabled=spec.reranker_enabled,
            requested_at=datetime.now(timezone.utc),
        )
        await self._registry.create(run)
        return run

    async def execute_run(self, run_id: str) -> EvaluationRunSnapshot:
        """Run one queued job off the event loop and persist its terminal state."""

        current = await self.get_run(run_id)
        if current.status in (
            EvaluationRunStatus.SUCCEEDED,
            EvaluationRunStatus.FAILED,
        ):
            return current
        started_at = datetime.now(timezone.utc)
        current = replace(
            current,
            status=EvaluationRunStatus.RUNNING,
            started_at=started_at,
            error_code=None,
            error_message=None,
        )
        await self._registry.update(current)
        if self._executor is None:
            return await self._fail(
                current,
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                "Evaluation executor is unavailable",
            )
        try:
            spec = EvaluationSpec(
                evaluation_type=current.evaluation_type,
                dataset=current.dataset,
                split=current.split,
                mode=current.mode,
                top_k=current.top_k,
                reranker_enabled=current.reranker_enabled,
            )
            execution = await asyncio.to_thread(self._executor.execute, spec)
            finished_at = datetime.now(timezone.utc)
            artifact_path = await asyncio.to_thread(
                self._write_artifact,
                current,
                execution,
                finished_at,
            )
            completed = replace(
                current,
                status=EvaluationRunStatus.SUCCEEDED,
                finished_at=finished_at,
                case_count=execution.case_count,
                metrics=execution.metrics,
                artifact_path=artifact_path,
                git_sha=_git_sha(self._repo_root),
            )
            await self._registry.update(completed)
            return completed
        except ServiceError as error:
            return await self._fail(current, error.code, error.message)
        except Exception as error:
            return await self._fail(
                current,
                ErrorCode.EVALUATION_FAILED,
                str(error) or "Evaluation run failed",
            )

    async def get_run(self, run_id: str) -> EvaluationRunSnapshot:
        """Return a run or a stable not-found error."""

        run = await self._registry.get(run_id)
        if run is None:
            raise ServiceError(
                code=ErrorCode.EVALUATION_NOT_FOUND,
                message="Evaluation run was not found",
            )
        return run

    async def list_runs(self, limit: int) -> tuple[EvaluationRunSnapshot, ...]:
        """Return the newest bounded evaluation snapshots."""

        return await self._registry.list(limit)

    async def _fail(
        self,
        current: EvaluationRunSnapshot,
        code: ErrorCode,
        message: str,
    ) -> EvaluationRunSnapshot:
        failed = replace(
            current,
            status=EvaluationRunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_code=code.value,
            error_message=message,
        )
        await self._registry.update(failed)
        return failed

    def _write_artifact(
        self,
        run: EvaluationRunSnapshot,
        execution: EvaluationExecution,
        finished_at: datetime,
    ) -> str:
        """Write raw observations with the requested configuration and SHA."""

        git_sha = _git_sha(self._repo_root)
        path = self._artifact_dir / f"{run.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run.run_id,
            "git_sha": git_sha,
            "finished_at": finished_at.isoformat(),
            "evaluation_type": run.evaluation_type,
            "dataset": run.dataset,
            "split": run.split,
            "mode": run.mode.value,
            "top_k": run.top_k,
            "reranker_enabled": run.reranker_enabled,
            "case_count": execution.case_count,
            "metrics": execution.metrics,
            "run": execution.raw,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(path)


def _scalar_metrics(raw: dict[str, object]) -> dict[str, MetricValue]:
    """Keep API metrics flat and JSON-safe while raw results stay complete."""

    allowed = (int, float, str, bool)
    return {
        key: value
        for key, value in raw.items()
        if value is None or isinstance(value, allowed)
    }


def _git_sha(repo_root: Path) -> str:
    """Return the source revision or an explicit unknown marker."""

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
