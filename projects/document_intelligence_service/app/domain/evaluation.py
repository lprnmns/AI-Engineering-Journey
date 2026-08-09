"""Framework-independent evaluation run state and result contracts."""

from dataclasses import dataclass
from datetime import datetime

from .entities import EvaluationRunStatus, RetrievalMode

MetricValue = int | float | str | bool | None


@dataclass(frozen=True, slots=True)
class EvaluationRunSnapshot:
    """Public state of one reproducible offline benchmark invocation."""

    run_id: str
    status: EvaluationRunStatus
    evaluation_type: str
    dataset: str
    split: str
    mode: RetrievalMode
    top_k: int
    reranker_enabled: bool
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    case_count: int | None = None
    metrics: dict[str, MetricValue] | None = None
    artifact_path: str | None = None
    git_sha: str | None = None
    error_code: str | None = None
    error_message: str | None = None
