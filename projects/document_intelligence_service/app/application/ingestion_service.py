"""Ingestion preparation use case."""

from ..domain.ingestion import (
    IngestionLimits,
    PipelineConfig,
    PreparedIngestion,
    compute_pipeline_fingerprint,
    validate_upload_metadata,
)
from .ports import PdfInspector


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
    ) -> PreparedIngestion:
        """Validate, inspect and calculate stable ingestion identities."""

        upload = validate_upload_metadata(
            content=content,
            filename=filename,
            content_type=content_type,
            limits=self._limits,
        )
        pdf = self._pdf_inspector.inspect(content, self._limits.max_pdf_pages)
        return PreparedIngestion(
            upload=upload,
            pdf=pdf,
            pipeline_fingerprint=compute_pipeline_fingerprint(self._pipeline_config),
        )
