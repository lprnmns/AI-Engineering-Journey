"""Ingestion preparation use case."""

import asyncio
import logging

from ..domain.ingestion import (
    IngestionReceipt,
    JobSnapshot,
    IngestionLimits,
    PipelineConfig,
    PreparedIngestion,
    compute_pipeline_fingerprint,
    validate_upload_metadata,
)
from .ports import IngestionRegistry, PdfInspector
from ..observability.audit import emit_audit


class IngestionPreparationService:
    """Prepare an upload identity before staging it in a vector store."""

    def __init__(
        self,
        *,
        limits: IngestionLimits,
        pipeline_config: PipelineConfig,
        pdf_inspector: PdfInspector,
    ) -> None:
        self._limits = limits
        self._pipeline_config = pipeline_config
        self._pdf_inspector = pdf_inspector

    def prepare(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        tenant_id: str | None = None,
        acl_tags: tuple[str, ...] = (),
    ) -> PreparedIngestion:
        """Validate, inspect and calculate stable ingestion identities."""

        upload = validate_upload_metadata(
            content=content,
            filename=filename,
            content_type=content_type,
            tenant_id=tenant_id,
            acl_tags=acl_tags,
            limits=self._limits,
        )
        pdf = self._pdf_inspector.inspect(content, self._limits.max_pdf_pages)
        return PreparedIngestion(
            content=content,
            upload=upload,
            pdf=pdf,
            pipeline_fingerprint=compute_pipeline_fingerprint(self._pipeline_config),
        )


class IngestionService:
    """Coordinate preparation and idempotent acceptance of uploads."""

    def __init__(
        self,
        *,
        preparation: IngestionPreparationService,
        registry: IngestionRegistry,
        max_upload_bytes: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._preparation = preparation
        self._registry = registry
        self._max_upload_bytes = max_upload_bytes
        self._logger = logger or logging.getLogger(
            "document_intelligence_service.ingestion"
        )

    @property
    def max_upload_bytes(self) -> int:
        """Expose the bounded read limit to the HTTP adapter."""

        return self._max_upload_bytes

    @property
    def registry(self) -> IngestionRegistry:
        """Expose the application port for composition of document reads."""

        return self._registry

    async def accept_receipt(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        idempotency_key: str | None,
        tenant_id: str | None = None,
        acl_tags: tuple[str, ...] = (),
    ) -> IngestionReceipt:
        """Prepare an upload and return its stable acceptance receipt."""

        # PDF inspection is synchronous and can take noticeable time for a
        # large upload. Keep that work off the API event loop so health and job
        # polling remain responsive while the request is being accepted.
        prepared = await asyncio.to_thread(
            self._preparation.prepare,
            content=content,
            filename=filename,
            content_type=content_type,
            tenant_id=tenant_id,
            acl_tags=acl_tags,
        )
        receipt = await self._registry.accept(prepared, idempotency_key)
        emit_audit(
            action="ingestion.accepted",
            result="accepted",
            document_id=receipt.document_id,
            version_id=receipt.version_id,
            tenant_id=prepared.upload.tenant_id,
            job_id=receipt.job_id,
            metadata={
                "bytes": prepared.upload.size_bytes,
                "pages": prepared.pdf.page_count,
            },
            logger=self._logger,
        )
        return receipt

    async def get_job(self, job_id: str) -> JobSnapshot:
        """Get a job or expose a stable not-found domain error."""

        from ..domain.errors import ErrorCode, ServiceError

        snapshot = await self._registry.get_job(job_id)
        if snapshot is None:
            raise ServiceError(
                code=ErrorCode.JOB_NOT_FOUND,
                message="Job was not found",
            )
        return snapshot
