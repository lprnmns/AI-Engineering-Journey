"""Ports implemented by infrastructure adapters."""

from typing import Protocol
from collections.abc import Sequence

from ..domain.entities import DocumentStatus
from ..domain.health import DependencyHealth
from ..domain.ingestion import (
    IngestionReceipt,
    JobSnapshot,
    PdfInspection,
    PreparedIngestion,
    StageEvent,
    VersionVerification,
)
from ..domain.generation import GeneratedAnswer
from ..domain.chunks import ChildChunk, PageText
from ..domain.retrieval import RetrievedChunk
from ..domain.vectors import SparseVector


class HealthProbe(Protocol):
    """Contract for checking one required dependency."""

    async def check(self) -> DependencyHealth:
        """Return the dependency's current health without raising."""

        ...


class PdfInspector(Protocol):
    """Port for page-aware PDF structure inspection."""

    def inspect(self, content: bytes, max_pages: int) -> PdfInspection:
        """Validate PDF structure and return bounded page metadata."""

        ...


class PageTextExtractor(Protocol):
    """Port for page-preserving selectable text extraction."""

    def extract(self, content: bytes) -> tuple[PageText, ...]:
        """Return normalized text while retaining page boundaries."""

        ...


class DenseEmbedder(Protocol):
    """Port for a dense embedding model loaded outside request handling."""

    @property
    def dimension(self) -> int:
        """Return the fixed output dimension of the embedding model."""

        ...

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        """Encode a bounded batch of texts into dense vectors."""

        ...


class SparseEmbedder(Protocol):
    """Port for a deterministic lexical/sparse encoder."""

    def embed_documents(self, texts: Sequence[str]) -> tuple[SparseVector, ...]:
        """Encode a bounded batch of texts into sparse vectors."""

        ...


class ChunkVectorStore(Protocol):
    """Port for staging and activating versioned retrieval chunks."""

    def stage_version(
        self,
        *,
        chunks: Sequence[ChildChunk],
        dense_vectors: Sequence[Sequence[float]],
        sparse_vectors: Sequence[SparseVector],
        pipeline_fingerprint: str,
        language: str,
    ) -> None:
        """Write a version as inactive points."""

        ...


    def verify_version(
        self,
        *,
        document_id: str,
        version_id: str,
        expected_chunk_count: int,
    ) -> VersionVerification:
        """Validate schema, point count and staged metadata."""

        ...

    def activate_version(
        self,
        *,
        document_id: str,
        version_id: str,
        verification: VersionVerification,
    ) -> None:
        """Make the verified version visible to retrieval."""

        ...


class ChunkRetriever(Protocol):
    """Port for active-version dense and sparse evidence search."""

    def search_dense(
        self,
        *,
        query_vector: Sequence[float],
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        """Return dense candidates from active points only."""

        ...

    def search_sparse(
        self,
        *,
        query_vector: SparseVector,
        limit: int,
        document_ids: Sequence[str],
    ) -> tuple[RetrievedChunk, ...]:
        """Return sparse candidates from active points only."""

        ...


class Reranker(Protocol):
    """Port for bounded question/evidence cross-encoder reranking."""

    def rerank(
        self,
        *,
        question: str,
        candidates: Sequence[RetrievedChunk],
        limit: int,
    ) -> tuple[RetrievedChunk, ...]:
        """Return the highest-scoring bounded evidence candidates."""

        ...


class AnswerGenerator(Protocol):
    """Port for grounded answer generation after the answerability gate."""

    async def generate(
        self,
        *,
        question: str,
        evidence: Sequence[RetrievedChunk],
    ) -> GeneratedAnswer:
        """Generate an answer using only the supplied evidence."""

        ...


class IngestionRegistry(Protocol):
    """Port for idempotent document and job state."""

    async def accept(
        self,
        prepared: PreparedIngestion,
        idempotency_key: str | None,
    ) -> IngestionReceipt:
        """Persist an accepted ingestion identity and return its receipt."""

        ...

    async def get_job(self, job_id: str) -> JobSnapshot | None:
        """Return one job snapshot, if it exists."""

        ...

    async def get_staged_content(self, job_id: str) -> bytes | None:
        """Return staged bytes for a future ingestion worker."""

        ...

    async def get_staged_ingestion(self, job_id: str) -> PreparedIngestion | None:
        """Return the complete staged ingestion identity for a worker."""

        ...

    async def update_job(self, snapshot: JobSnapshot) -> None:
        """Persist a worker progress transition."""

        ...

    async def record_stage_event(self, job_id: str, event: StageEvent) -> None:
        """Persist a stage transition and expose its latest snapshot."""

        ...

    async def set_document_status(
        self,
        *,
        document_id: str,
        version_id: str,
        status: DocumentStatus,
    ) -> None:
        """Persist the lifecycle of one version independently from its job."""

        ...
