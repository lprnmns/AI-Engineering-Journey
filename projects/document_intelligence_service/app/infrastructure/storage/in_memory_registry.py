"""Development registry for idempotent ingestion acceptance.

This adapter is intentionally replaceable. It is not restart-safe and will be
replaced by durable document/job persistence before production deployment.
"""

import asyncio
from dataclasses import dataclass

from ...domain.entities import DocumentStatus, JobStatus
from ...domain.errors import ErrorCode, ServiceError
from ...domain.ingestion import (
    IngestionReceipt,
    JobSnapshot,
    PreparedIngestion,
    create_ingestion_receipt,
    normalize_idempotency_key,
)


@dataclass(slots=True)
class _StoredIngestion:
    receipt: IngestionReceipt
    identity: tuple[str, str]
    prepared: PreparedIngestion


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
        normalized_key = normalize_idempotency_key(idempotency_key)
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

            receipt = create_ingestion_receipt(identity)
            stored = _StoredIngestion(
                receipt=receipt,
                identity=identity,
                prepared=prepared,
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

    async def get_staged_ingestion(self, job_id: str) -> PreparedIngestion | None:
        """Return the complete staged identity for the ingestion worker."""

        async with self._lock:
            for stored in self._by_identity.values():
                if stored.receipt.job_id == job_id:
                    return stored.prepared
        return None

    async def update_job(self, snapshot: JobSnapshot) -> None:
        """Replace one job snapshot under the same registry lock."""

        async with self._lock:
            if snapshot.job_id not in self._jobs:
                raise KeyError(f"unknown job: {snapshot.job_id}")
            self._jobs[snapshot.job_id] = snapshot

    async def set_document_status(
        self,
        *,
        document_id: str,
        version_id: str,
        status: DocumentStatus,
    ) -> None:
        """Update the receipt status without changing job progress."""

        async with self._lock:
            for stored in self._by_identity.values():
                if (
                    stored.receipt.document_id == document_id
                    and stored.receipt.version_id == version_id
                ):
                    stored.receipt = IngestionReceipt(
                        document_id=document_id,
                        version_id=version_id,
                        job_id=stored.receipt.job_id,
                        status=status,
                    )
                    return
        raise KeyError(f"unknown document version: {document_id}/{version_id}")
