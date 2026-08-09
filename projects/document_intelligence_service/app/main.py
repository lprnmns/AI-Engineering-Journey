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
from .application.chunking_service import DocumentChunkingService
from .application.document_service import DocumentService
from .application.ingestion_service import (
    IngestionPreparationService,
    IngestionService,
)
from .application.ingestion_worker import IngestionWorker
from .application.query_service import QueryService
from .application.retrieval_service import RetrievalService
from .application.ports import IngestionRegistry
from .domain.errors import ServiceError
from .domain.answerability import AnswerabilityPolicy
from .domain.ingestion import IngestionLimits, PipelineConfig
from .infrastructure.health_checks import HttpHealthProbe
from .infrastructure.embeddings.dense import SentenceTransformerEmbedder
from .infrastructure.embeddings.sparse import HashingSparseEncoder
from .infrastructure.parsing.pdf_inspector import PypdfInspector
from .infrastructure.parsing.pdf_text import PypdfTextExtractor
from .infrastructure.parsing.section_markers import get_section_markers
from .infrastructure.qdrant.chunk_store import QdrantChunkStore
from .infrastructure.qdrant.retriever import QdrantRetriever
from .infrastructure.reranking.cross_encoder import CrossEncoderReranker
from .infrastructure.ollama.answer_generator import OllamaAnswerGenerator
from .infrastructure.qdrant.schema import QdrantSchema
from .infrastructure.storage.in_memory_registry import InMemoryIngestionRegistry
from .infrastructure.storage.sqlite_registry import SqliteIngestionRegistry
from qdrant_client import QdrantClient
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


def build_ingestion_registry(settings: Settings) -> IngestionRegistry:
    """Choose the registry implementation without changing application code."""

    if settings.ingestion_registry_backend == "sqlite":
        return SqliteIngestionRegistry(settings.ingestion_database_path)
    return InMemoryIngestionRegistry()


def build_document_service(
    settings: Settings,
    *,
    registry: IngestionRegistry | None = None,
) -> DocumentService:
    """Wire document metadata and vector cleanup to the same registry."""

    return DocumentService(
        registry=registry if registry is not None else build_ingestion_registry(settings),
        vector_store=QdrantChunkStore(
            QdrantClient(url=str(settings.qdrant_url)),
            QdrantSchema(),
        ),
    )


def build_pipeline_config(settings: Settings) -> PipelineConfig:
    """Build one shared fingerprint configuration for ingestion stages."""

    return PipelineConfig(section_marker_profile=settings.section_marker_profile)


def build_ingestion_service(
    settings: Settings,
    *,
    registry: IngestionRegistry | None = None,
) -> IngestionService:
    """Wire the preparation use case to a selectable persistence adapter."""

    pipeline_config = build_pipeline_config(settings)
    preparation = IngestionPreparationService(
        limits=IngestionLimits(
            max_upload_bytes=settings.max_upload_bytes,
            max_pdf_pages=settings.max_pdf_pages,
        ),
        pipeline_config=pipeline_config,
        pdf_inspector=PypdfInspector(),
    )
    return IngestionService(
        preparation=preparation,
        registry=registry
        if registry is not None
        else build_ingestion_registry(settings),
        max_upload_bytes=settings.max_upload_bytes,
    )


def build_ingestion_worker(
    settings: Settings,
    *,
    registry: IngestionRegistry,
) -> IngestionWorker:
    """Wire the lazy embedding, parser and Qdrant worker adapters."""

    pipeline_config = build_pipeline_config(settings)
    schema = QdrantSchema()
    return IngestionWorker(
        registry=registry,
        chunker=DocumentChunkingService(
            extractor=PypdfTextExtractor(),
            pipeline_config=pipeline_config,
        ),
        dense_embedder=SentenceTransformerEmbedder(
            model_name=pipeline_config.embedding_model,
            expected_dimension=schema.dense_size,
        ),
        sparse_embedder=HashingSparseEncoder(),
        vector_store=QdrantChunkStore(
            QdrantClient(url=str(settings.qdrant_url)),
            schema,
        ),
        section_markers=get_section_markers(settings.section_marker_profile),
    )


def build_retrieval_service(settings: Settings) -> RetrievalService:
    """Wire lazy query embedders to the active-version Qdrant retriever."""

    pipeline_config = build_pipeline_config(settings)
    schema = QdrantSchema()
    return RetrievalService(
        dense_embedder=SentenceTransformerEmbedder(
            model_name=pipeline_config.embedding_model,
            expected_dimension=schema.dense_size,
        ),
        sparse_embedder=HashingSparseEncoder(),
        retriever=QdrantRetriever(
            QdrantClient(url=str(settings.qdrant_url)),
            schema,
        ),
        reranker=(
            CrossEncoderReranker(model_name=pipeline_config.reranker_model)
            if settings.reranker_enabled
            else None
        ),
    )


def build_query_service(
    settings: Settings,
    *,
    retrieval_service: RetrievalService | None = None,
) -> QueryService:
    """Wire answerability policy and the host-local Ollama boundary."""

    return QueryService(
        retrieval_service=retrieval_service
        if retrieval_service is not None
        else build_retrieval_service(settings),
        answerability=AnswerabilityPolicy(
            min_dense_score=settings.answerability_min_dense_score,
            min_sparse_score=settings.answerability_min_sparse_score,
            min_rerank_score=settings.answerability_min_rerank_score,
            min_margin=settings.answerability_min_margin,
            min_coverage=settings.answerability_min_coverage,
        ),
        answer_generator=OllamaAnswerGenerator(
            base_url=str(settings.ollama_url),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        ),
    )


def create_app(
    *,
    settings: Settings | None = None,
    health_service: HealthService | None = None,
    ingestion_service: IngestionService | None = None,
    ingestion_worker: IngestionWorker | None = None,
    document_service: DocumentService | None = None,
    retrieval_service: RetrievalService | None = None,
    query_service: QueryService | None = None,
) -> FastAPI:
    """Create an application with replaceable dependencies for testing."""

    resolved_settings = settings or Settings()
    resolved_health_service = health_service or build_health_service(resolved_settings)
    resolved_ingestion_worker = ingestion_worker
    resolved_document_service = document_service
    resolved_retrieval_service = retrieval_service
    resolved_query_service = query_service
    if ingestion_service is None:
        registry = build_ingestion_registry(resolved_settings)
        resolved_ingestion_service = build_ingestion_service(
            resolved_settings,
            registry=registry,
        )
        if resolved_document_service is None:
            resolved_document_service = build_document_service(
                resolved_settings,
                registry=registry,
            )
        if (
            resolved_ingestion_worker is None
            and resolved_settings.ingestion_registry_backend == "sqlite"
        ):
            resolved_ingestion_worker = build_ingestion_worker(
                resolved_settings,
                registry=registry,
            )
        if (
            resolved_retrieval_service is None
            and resolved_settings.ingestion_registry_backend == "sqlite"
        ):
            resolved_retrieval_service = build_retrieval_service(resolved_settings)
        if (
            resolved_query_service is None
            and resolved_retrieval_service is not None
        ):
            resolved_query_service = build_query_service(
                resolved_settings,
                retrieval_service=resolved_retrieval_service,
            )
    else:
        resolved_ingestion_service = ingestion_service
        if resolved_document_service is None:
            resolved_document_service = DocumentService(
                registry=ingestion_service.registry,
            )
        if (
            resolved_query_service is None
            and resolved_retrieval_service is not None
        ):
            resolved_query_service = build_query_service(
                resolved_settings,
                retrieval_service=resolved_retrieval_service,
            )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.health_service = resolved_health_service
        application.state.ingestion_service = resolved_ingestion_service
        application.state.ingestion_worker = resolved_ingestion_worker
        application.state.document_service = resolved_document_service
        application.state.retrieval_service = resolved_retrieval_service
        application.state.query_service = resolved_query_service
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
    application.state.ingestion_worker = resolved_ingestion_worker
    application.state.document_service = resolved_document_service
    application.state.retrieval_service = resolved_retrieval_service
    application.state.query_service = resolved_query_service
    application.include_router(health_router, prefix="/v1")
    application.include_router(documents_router, prefix="/v1")
    application.include_router(jobs_router, prefix="/v1")
    application.include_router(queries_router, prefix="/v1")
    application.include_router(search_router, prefix="/v1")
    return application


app = create_app()
