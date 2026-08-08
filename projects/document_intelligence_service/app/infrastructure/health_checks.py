"""HTTP health probes for Qdrant and Ollama."""

from time import perf_counter

import httpx

from ..domain.health import DependencyHealth, DependencyState


class HttpHealthProbe:
    """Check an HTTP dependency and convert failures into domain state."""

    def __init__(self, *, name: str, url: str, timeout_seconds: float) -> None:
        self._name = name
        self._url = url
        self._timeout_seconds = timeout_seconds

    async def check(self) -> DependencyHealth:
        """Return health state without leaking connection details."""

        started_at = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(self._url)
                response.raise_for_status()
        except (httpx.HTTPError, OSError):
            return DependencyHealth(
                name=self._name,
                state=DependencyState.DOWN,
                latency_ms=_elapsed_ms(started_at),
                detail="dependency unavailable",
            )

        return DependencyHealth(
            name=self._name,
            state=DependencyState.UP,
            latency_ms=_elapsed_ms(started_at),
        )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)
