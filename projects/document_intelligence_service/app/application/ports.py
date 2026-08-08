"""Ports implemented by infrastructure adapters."""

from typing import Protocol

from ..domain.health import DependencyHealth
from ..domain.ingestion import (
    IngestionReceipt,
    JobSnapshot,
    PdfInspection,
    PreparedIngestion,
)
from ..domain.chunks import PageText


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
