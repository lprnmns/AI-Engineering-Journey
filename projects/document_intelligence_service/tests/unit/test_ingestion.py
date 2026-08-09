"""Unit tests for Day 2 ingestion identity and validation."""

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from projects.document_intelligence_service.app.domain.entities import JobStatus
from projects.document_intelligence_service.app.application.ingestion_service import (
    IngestionPreparationService,
)
from projects.document_intelligence_service.app.domain.errors import (
    ErrorCode,
    ServiceError,
)
from projects.document_intelligence_service.app.domain.ingestion import (
    IngestionLimits,
    JobSnapshot,
    PipelineConfig,
    compute_content_hash,
    compute_pipeline_fingerprint,
    validate_upload_metadata,
)
from projects.document_intelligence_service.app.infrastructure.parsing.pdf_inspector import (
    PypdfInspector,
)
from projects.document_intelligence_service.app.infrastructure.storage.in_memory_registry import (
    InMemoryIngestionRegistry,
)
from projects.document_intelligence_service.app.infrastructure.storage.sqlite_registry import (
    SqliteIngestionRegistry,
)


def make_pdf(page_count: int = 1) -> bytes:
    """Create a small valid PDF fixture in memory."""

    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_content_hash_is_stable_and_changes_with_bytes() -> None:
    assert compute_content_hash(b"same") == compute_content_hash(b"same")
    assert compute_content_hash(b"same") != compute_content_hash(b"changed")


def test_pipeline_fingerprint_changes_when_chunker_changes() -> None:
    base = PipelineConfig()
    changed = PipelineConfig(chunker="fixed_token_v2")

    assert compute_pipeline_fingerprint(base) == compute_pipeline_fingerprint(base)
    assert compute_pipeline_fingerprint(base) != compute_pipeline_fingerprint(changed)


def test_pipeline_fingerprint_changes_when_section_profile_changes() -> None:
    base = PipelineConfig(section_marker_profile="none")
    mentor = PipelineConfig(section_marker_profile="mentor_program_v1")

    assert compute_pipeline_fingerprint(base) != compute_pipeline_fingerprint(mentor)


def test_upload_metadata_validates_pdf_and_sanitizes_filename() -> None:
    metadata = validate_upload_metadata(
        content=make_pdf(),
        filename="/tmp\\private\\report.pdf",
        content_type="application/pdf; charset=binary",
        limits=IngestionLimits(),
    )

    assert metadata.filename == "report.pdf"
    assert metadata.content_type == "application/pdf"
    assert metadata.size_bytes > 0
    assert len(metadata.content_hash) == 64


@pytest.mark.parametrize(
    ("content", "filename", "content_type", "expected_code"),
    [
        (b"%PDF-1.7", "report.pdf", "text/plain", ErrorCode.UNSUPPORTED_MEDIA_TYPE),
        (b"not a pdf", "report.pdf", "application/pdf", ErrorCode.DOCUMENT_PARSE_FAILED),
        (b"%PDF-1.7", "report.txt", "application/pdf", ErrorCode.UNSUPPORTED_MEDIA_TYPE),
    ],
)
def test_upload_metadata_rejects_unsafe_input(
    content: bytes,
    filename: str,
    content_type: str,
    expected_code: ErrorCode,
) -> None:
    with pytest.raises(ServiceError) as raised:
        validate_upload_metadata(
            content=content,
            filename=filename,
            content_type=content_type,
            limits=IngestionLimits(),
        )

    assert raised.value.code is expected_code


def test_upload_size_limit_is_checked_before_pdf_parsing() -> None:
    with pytest.raises(ServiceError) as raised:
        validate_upload_metadata(
            content=b"%PDF-1.7" + b"x" * 20,
            filename="report.pdf",
            content_type="application/pdf",
            limits=IngestionLimits(max_upload_bytes=10),
        )

    assert raised.value.code is ErrorCode.UPLOAD_TOO_LARGE


def test_pypdf_inspector_returns_page_count_and_enforces_limit() -> None:
    inspector = PypdfInspector()

    assert inspector.inspect(make_pdf(page_count=2), max_pages=2).page_count == 2
    with pytest.raises(ServiceError) as raised:
        inspector.inspect(make_pdf(page_count=2), max_pages=1)

    assert raised.value.code is ErrorCode.DOCUMENT_PARSE_FAILED


def test_preparation_service_combines_upload_pdf_and_pipeline_identity() -> None:
    service = IngestionPreparationService(
        limits=IngestionLimits(),
        pipeline_config=PipelineConfig(),
        pdf_inspector=PypdfInspector(),
    )

    prepared = service.prepare(
        content=make_pdf(page_count=2),
        filename="guide.pdf",
        content_type="application/pdf",
    )

    assert prepared.pdf.page_count == 2
    assert len(prepared.upload.content_hash) == 64
    assert len(prepared.pipeline_fingerprint) == 64


def test_development_registry_keeps_staged_bytes_for_future_worker() -> None:
    content = make_pdf()
    preparation = IngestionPreparationService(
        limits=IngestionLimits(),
        pipeline_config=PipelineConfig(),
        pdf_inspector=PypdfInspector(),
    )
    prepared = preparation.prepare(
        content=content,
        filename="guide.pdf",
        content_type="application/pdf",
    )
    registry = InMemoryIngestionRegistry()

    receipt = asyncio.run(registry.accept(prepared, "stage-1"))
    staged = asyncio.run(registry.get_staged_content(receipt.job_id))

    assert staged == content


def test_sqlite_registry_survives_a_new_registry_instance(tmp_path: Path) -> None:
    content = make_pdf()
    preparation = IngestionPreparationService(
        limits=IngestionLimits(),
        pipeline_config=PipelineConfig(),
        pdf_inspector=PypdfInspector(),
    )
    prepared = preparation.prepare(
        content=content,
        filename="guide.pdf",
        content_type="application/pdf",
    )
    database_path = tmp_path / "state" / "ingestions.sqlite3"

    first_registry = SqliteIngestionRegistry(database_path)
    first_receipt = asyncio.run(first_registry.accept(prepared, "durable-1"))
    queued = asyncio.run(first_registry.get_job(first_receipt.job_id))
    asyncio.run(
        first_registry.update_job(
            JobSnapshot(
                job_id=first_receipt.job_id,
                document_id=first_receipt.document_id,
                status=JobStatus.RUNNING,
                progress_percent=35,
                error_code=None,
            )
        )
    )

    restarted_registry = SqliteIngestionRegistry(database_path)
    restored = asyncio.run(restarted_registry.get_job(first_receipt.job_id))
    restored_content = asyncio.run(
        restarted_registry.get_staged_content(first_receipt.job_id)
    )
    retried = asyncio.run(restarted_registry.accept(prepared, "durable-1"))

    assert queued is not None
    assert queued.status is JobStatus.QUEUED
    assert restored is not None
    assert restored.status is JobStatus.RUNNING
    assert restored.progress_percent == 35
    assert restored_content == content
    assert retried == first_receipt
