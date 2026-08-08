"""FastAPI composition root for the document intelligence service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .api.errors import service_error_handler, validation_error_handler
from .api.v1.health import router as health_router
from .api.v1.documents import router as documents_router
from .api.v1.jobs import router as jobs_router
from .api.v1.queries import router as queries_router
from .api.v1.search import router as search_router
from .application.health_service import HealthService
from .application.ingestion_service import (
    IngestionPreparationService,
    IngestionService,
)
from .domain.errors import ServiceError
from .domain.ingestion import IngestionLimits, PipelineConfig
from .infrastructure.health_checks import HttpHealthProbe
from .infrastructure.parsing.pdf_inspector import PypdfInspector
from .infrastructure.storage.in_memory_registry import InMemoryIngestionRegistry
from .observability.request_id import RequestIdMiddleware
from .settings import Settings


def build_health_service(settings: Settings) -> HealthService:
    """Wire concrete dependency probes into the application service."""

    timeout = settings.dependency_timeout_seconds
    return HealthService(
        probes=(
            HttpHealthProbe(
                name="qdrant",
                url=f"{str(settings.qdrant_url).rstrip('/')}/readyz",
                timeout_seconds=timeout,
            ),
            HttpHealthProbe(
                name="ollama",
                url=f"{str(settings.ollama_url).rstrip('/')}/api/tags",
                timeout_seconds=timeout,
            ),
        )
    )


def build_ingestion_service(settings: Settings) -> IngestionService:
    """Wire the Day 2 preparation use case and development registry."""

    preparation = IngestionPreparationService(
        limits=IngestionLimits(
            max_upload_bytes=settings.max_upload_bytes,
            max_pdf_pages=settings.max_pdf_pages,
        ),
        pipeline_config=PipelineConfig(),
        pdf_inspector=PypdfInspector(),
    )
    return IngestionService(
        preparation=preparation,
        registry=InMemoryIngestionRegistry(),
        max_upload_bytes=settings.max_upload_bytes,
    )


def create_app(
    *,
    settings: Settings | None = None,
    health_service: HealthService | None = None,
    ingestion_service: IngestionService | None = None,
) -> FastAPI:
    """Create an application with replaceable dependencies for testing."""

    resolved_settings = settings or Settings()
    resolved_health_service = health_service or build_health_service(resolved_settings)
    resolved_ingestion_service = ingestion_service or build_ingestion_service(
        resolved_settings
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.health_service = resolved_health_service
        application.state.ingestion_service = resolved_ingestion_service
        resolved_health_service.mark_started()
        try:
            yield
        finally:
            resolved_health_service.mark_stopped()

    application = FastAPI(
        title="Document Intelligence Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(ServiceError, service_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.state.health_service = resolved_health_service
    application.state.ingestion_service = resolved_ingestion_service
    application.include_router(health_router, prefix="/v1")
    application.include_router(documents_router, prefix="/v1")
    application.include_router(jobs_router, prefix="/v1")
    application.include_router(queries_router, prefix="/v1")
    application.include_router(search_router, prefix="/v1")
    return application


app = create_app()
