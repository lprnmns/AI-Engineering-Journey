"""Ports implemented by infrastructure adapters."""

from typing import Protocol

from ..domain.health import DependencyHealth


class HealthProbe(Protocol):
    """Contract for checking one required dependency."""

    async def check(self) -> DependencyHealth:
        """Return the dependency's current health without raising."""

        ...
