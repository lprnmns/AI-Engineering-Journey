"""Contract tests for versioned health endpoints."""

import asyncio

import httpx
from fastapi import FastAPI

from projects.document_intelligence_service.app.application.health_service import (
    HealthService,
)
from projects.document_intelligence_service.app.domain.health import (
    DependencyHealth,
    DependencyState,
)
from projects.document_intelligence_service.app.main import create_app


class FakeProbe:
    """Probe with an observable call count for contract tests."""

    def __init__(self, result: DependencyHealth) -> None:
        self.result = result
        self.call_count = 0

    async def check(self) -> DependencyHealth:
        self.call_count += 1
        return self.result


async def request(app: FastAPI, path: str) -> httpx.Response:
    """Call the ASGI app while running its real lifespan hooks."""

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)


def test_liveness_returns_200_without_calling_dependencies() -> None:
    probe = FakeProbe(DependencyHealth("qdrant", DependencyState.DOWN, 0.0))
    app = create_app(health_service=HealthService((probe,)))

    response = asyncio.run(request(app, "/v1/health/live"))

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert probe.call_count == 0


def test_readiness_returns_503_with_safe_dependency_details() -> None:
    qdrant = FakeProbe(
        DependencyHealth(
            "qdrant",
            DependencyState.DOWN,
            3.5,
            detail="dependency unavailable",
        )
    )
    ollama = FakeProbe(DependencyHealth("ollama", DependencyState.UP, 4.0))
    app = create_app(health_service=HealthService((qdrant, ollama)))

    response = asyncio.run(request(app, "/v1/health/ready"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "qdrant": {
                "status": "down",
                "latency_ms": 3.5,
                "detail": "dependency unavailable",
            },
            "ollama": {"status": "up", "latency_ms": 4.0, "detail": None},
        },
    }


def test_startup_is_ready_inside_application_lifespan() -> None:
    app = create_app(health_service=HealthService(()))

    response = asyncio.run(request(app, "/v1/health/startup"))

    assert response.status_code == 200
    assert response.json() == {"status": "started"}
