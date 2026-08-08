"""Contract tests for resource, job and query routes."""

import asyncio

import httpx
from fastapi import FastAPI

from projects.document_intelligence_service.app.application.health_service import (
    HealthService,
)
from projects.document_intelligence_service.app.main import create_app


async def post_json(app: FastAPI, path: str, payload: object) -> httpx.Response:
    """POST JSON through the real ASGI lifespan and middleware."""

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"X-Request-ID": "contract-1"},
        ) as client:
            return await client.post(path, json=payload)


def test_valid_query_does_not_fabricate_an_answer_before_wiring() -> None:
    app = create_app(health_service=HealthService(()))

    response = asyncio.run(
        post_json(
            app,
            "/v1/query",
            {"question": "Qdrant ne işe yarar?"},
        )
    )

    assert response.status_code == 501
    assert response.json() == {
        "error": {
            "code": "FEATURE_NOT_READY",
            "message": "Query workflow is not wired yet",
            "request_id": "contract-1",
        }
    }


def test_invalid_query_uses_common_validation_envelope() -> None:
    app = create_app(health_service=HealthService(()))

    response = asyncio.run(post_json(app, "/v1/query", {"question": ""}))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.json()["error"]["request_id"] == "contract-1"
