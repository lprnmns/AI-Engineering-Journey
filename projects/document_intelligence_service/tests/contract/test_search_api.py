"""Contract tests for the evidence-only search endpoint."""

import asyncio

import httpx
from fastapi import FastAPI

from projects.document_intelligence_service.app.application.health_service import (
    HealthService,
)
from projects.document_intelligence_service.app.main import create_app
from projects.document_intelligence_service.tests.unit.test_retrieval_service import (
    make_service,
)


async def post_search(app: FastAPI, payload: object) -> httpx.Response:
    """Post one search through the real request-id middleware and lifespan."""

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"X-Request-ID": "search-contract-1"},
        ) as client:
            return await client.post("/v1/search", json=payload)


def test_search_returns_evidence_without_llm_fields() -> None:
    app = create_app(
        health_service=HealthService(()),
        retrieval_service=make_service(),
    )

    response = asyncio.run(
        post_search(
            app,
            {
                "question": "Qdrant ne işe yarar?",
                "retrieval_mode": "hybrid",
                "top_k": 3,
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "search-contract-1"
    assert body["retrieval"] == {
        "mode": "hybrid",
        "dense_candidates": 2,
        "sparse_candidates": 2,
        "rrf_candidates": 3,
        "reranked_candidates": 0,
    }
    assert body["sources"][0]["source_id"] == "shared"
    assert body["latency"]["llm_ms"] == 0


def test_search_does_not_silently_ignore_acl_filters() -> None:
    app = create_app(
        health_service=HealthService(()),
        retrieval_service=make_service(),
    )

    response = asyncio.run(
        post_search(
            app,
            {
                "question": "Qdrant ne işe yarar?",
                "acl_tags": ["finance"],
            },
        )
    )

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "FEATURE_NOT_READY"
