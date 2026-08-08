"""Tests for the stage -> verify -> activate ingestion worker."""

import asyncio
from io import BytesIO
from typing import Sequence

import pytest
from pypdf import PdfWriter

from projects.document_intelligence_service.app.application.chunking_service import (
    DocumentChunkingService,
)
from projects.document_intelligence_service.app.application.ingestion_service import (
    IngestionPreparationService,
)
from projects.document_intelligence_service.app.application.ingestion_worker import (
    IngestionWorker,
)
from projects.document_intelligence_service.app.domain.chunks import PageText
from projects.document_intelligence_service.app.domain.ingestion import (
    IngestionLimits,
    PipelineConfig,
)
from projects.document_intelligence_service.app.domain.vectors import SparseVector
from projects.document_intelligence_service.app.infrastructure.parsing.pdf_inspector import (
    PypdfInspector,
)
from projects.document_intelligence_service.app.infrastructure.qdrant.chunk_store import (
    QdrantChunkStore,
)
from projects.document_intelligence_service.app.infrastructure.qdrant.schema import (
    QdrantSchema,
)
from projects.document_intelligence_service.app.infrastructure.storage.in_memory_registry import (
    InMemoryIngestionRegistry,
)
from qdrant_client import QdrantClient


def make_pdf() -> bytes:
    """Create a structurally valid PDF for the preparation step."""

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class FakeExtractor:
    """Return stable text while avoiding a model or OCR dependency in tests."""

    def extract(self, content: bytes) -> tuple[PageText, ...]:
        assert content
        return (
            PageText(1, "RAG sistemi kanıt arar. Qdrant point saklar. Model cevap yazar."),
        )


class EmptyExtractor:
    """Return no selectable text so the domain parse guard is exercised."""

    def extract(self, content: bytes) -> tuple[PageText, ...]:
        assert content
        return ()


class FakeDenseEmbedder:
    """Small deterministic dense encoder for the worker integration test."""

    dimension = 2

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class FakeSparseEmbedder:
    """Small deterministic sparse encoder for the worker integration test."""

    def embed_documents(self, texts: Sequence[str]) -> tuple[SparseVector, ...]:
        return tuple(
            SparseVector(indices=(1, 2), values=(1.0, 0.5)) for _ in texts
        )


@pytest.mark.filterwarnings("ignore:Payload indexes have no effect in the local Qdrant")
def test_worker_stages_verifies_and_activates_a_version() -> None:
    preparation = IngestionPreparationService(
        limits=IngestionLimits(),
        pipeline_config=PipelineConfig(
            chunk_size_sentences=2,
            chunk_overlap_sentences=1,
        ),
        pdf_inspector=PypdfInspector(),
    )
    prepared = preparation.prepare(
        content=make_pdf(),
        filename="guide.pdf",
        content_type="application/pdf",
    )
    registry = InMemoryIngestionRegistry()
    receipt = asyncio.run(registry.accept(prepared, "worker-1"))
    store = QdrantChunkStore(
        QdrantClient(":memory:"),
        QdrantSchema(collection_name="worker_test", dense_size=2),
    )
    worker = IngestionWorker(
        registry=registry,
        chunker=DocumentChunkingService(
            extractor=FakeExtractor(),
            pipeline_config=PipelineConfig(
                chunk_size_sentences=2,
                chunk_overlap_sentences=1,
            ),
        ),
        dense_embedder=FakeDenseEmbedder(),
        sparse_embedder=FakeSparseEmbedder(),
        vector_store=store,
    )

    snapshot = asyncio.run(worker.run_job(receipt.job_id))

    assert snapshot.status.value == "succeeded"
    assert snapshot.progress_percent == 100
    assert snapshot.error_code is None
    assert store.client.count(store.collection_name, exact=True).count == 2


def test_worker_marks_empty_pdf_text_as_failed_without_indexing() -> None:
    preparation = IngestionPreparationService(
        limits=IngestionLimits(),
        pipeline_config=PipelineConfig(),
        pdf_inspector=PypdfInspector(),
    )
    prepared = preparation.prepare(
        content=make_pdf(),
        filename="empty.pdf",
        content_type="application/pdf",
    )
    registry = InMemoryIngestionRegistry()
    receipt = asyncio.run(registry.accept(prepared, "worker-empty"))
    store = QdrantChunkStore(
        QdrantClient(":memory:"),
        QdrantSchema(collection_name="worker_empty_test", dense_size=2),
    )
    worker = IngestionWorker(
        registry=registry,
        chunker=DocumentChunkingService(
            extractor=EmptyExtractor(),
            pipeline_config=PipelineConfig(),
        ),
        dense_embedder=FakeDenseEmbedder(),
        sparse_embedder=FakeSparseEmbedder(),
        vector_store=store,
    )

    snapshot = asyncio.run(worker.run_job(receipt.job_id))

    assert snapshot.status.value == "failed"
    assert snapshot.error_code == "DOCUMENT_PARSE_FAILED"
    assert not store.client.collection_exists("worker_empty_test")
