"""Ports implemented by infrastructure adapters."""

from typing import Protocol

from ..domain.health import DependencyHealth
from ..domain.ingestion import PdfInspection


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
