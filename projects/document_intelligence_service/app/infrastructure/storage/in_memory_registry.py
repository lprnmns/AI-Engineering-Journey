"""Development registry for idempotent ingestion acceptance.

This adapter is intentionally replaceable. It is not restart-safe and will be
replaced by durable document/job persistence before production deployment.
"""

import asyncio
from dataclasses import dataclass
import hashlib
from uuid import uuid4

from ...domain.entities import DocumentStatus, JobStatus
from ...domain.errors import ErrorCode, ServiceError
from ...domain.ingestion import IngestionReceipt, JobSnapshot, PreparedIngestion


@dataclass(frozen=True, slots=True)
class _StoredIngestion:
    receipt: IngestionReceipt
    identity: tuple[str, str]
    content: bytes


class InMemoryIngestionRegistry:
    """Bounded development state with atomic duplicate checks."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_identity: dict[tuple[str, str], _StoredIngestion] = {}
        self._by_idempotency: dict[str, _StoredIngestion] = {}
        self._idempotency_identity: dict[str, tuple[str, str]] = {}
        self._jobs: dict[str, JobSnapshot] = {}
        self._content_by_job: dict[str, bytes] = {}

    async def accept(
        self,
        prepared: PreparedIngestion,
        idempotency_key: str | None,
    ) -> IngestionReceipt:
        """Return an existing receipt or atomically create one."""

        identity = (
            prepared.upload.content_hash,
            prepared.pipeline_fingerprint,
        )
        normalized_key = _normalize_idempotency_key(idempotency_key)
        async with self._lock:
            if normalized_key is not None:
                previous_identity = self._idempotency_identity.get(normalized_key)
                if previous_identity is not None and previous_identity != identity:
                    raise ServiceError(
                        code=ErrorCode.INGESTION_CONFLICT,
                        message="Idempotency-Key was already used for another upload",
                    )
                existing_by_key = self._by_idempotency.get(normalized_key)
                if existing_by_key is not None:
                    return existing_by_key.receipt

            existing = self._by_identity.get(identity)
            if existing is not None:
                if normalized_key is not None:
                    self._by_idempotency[normalized_key] = existing
                    self._idempotency_identity[normalized_key] = identity
                return existing.receipt

            receipt = _create_receipt(identity)
            stored = _StoredIngestion(
                receipt=receipt,
                identity=identity,
                content=prepared.content,
            )
            self._by_identity[identity] = stored
            if normalized_key is not None:
                self._by_idempotency[normalized_key] = stored
                self._idempotency_identity[normalized_key] = identity
            self._jobs[receipt.job_id] = JobSnapshot(
                job_id=receipt.job_id,
                document_id=receipt.document_id,
                status=JobStatus.QUEUED,
                progress_percent=0,
                error_code=None,
            )
            self._content_by_job[receipt.job_id] = prepared.content
            return receipt

    async def get_job(self, job_id: str) -> JobSnapshot | None:
        """Return a queued job snapshot, if known."""

        async with self._lock:
            return self._jobs.get(job_id)

    async def get_staged_content(self, job_id: str) -> bytes | None:
        """Return staged bytes for a future worker in this process."""

        async with self._lock:
            return self._content_by_job.get(job_id)


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise ServiceError(
            code=ErrorCode.INVALID_REQUEST,
            message="Idempotency-Key is too long",
        )
    return normalized


def _create_receipt(identity: tuple[str, str]) -> IngestionReceipt:
    content_hash, pipeline_fingerprint = identity
    version_digest = hashlib.sha256(
        f"{content_hash}:{pipeline_fingerprint}".encode("ascii")
    ).hexdigest()
    return IngestionReceipt(
        document_id=f"doc_{content_hash}",
        version_id=f"ver_{version_digest}",
        job_id=f"job_{uuid4().hex}",
        status=DocumentStatus.INDEXING,
    )
