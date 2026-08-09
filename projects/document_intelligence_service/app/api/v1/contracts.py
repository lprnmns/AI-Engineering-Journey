"""Version 1 request and response contracts.

These models define the external API before application implementations are
connected. They intentionally contain no Qdrant, embedding or Ollama types.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.entities import (
    Decision,
    DocumentStatus,
    JobStatus,
    NoAnswerReason,
    RetrievalMode,
)
from ...domain.evidence_validation import EvidenceWarningCode


class PageQuery(BaseModel):
    """Bounded cursor pagination shared by list endpoints."""

    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=256)


class DocumentUploadResponse(BaseModel):
    """Accepted asynchronous document ingestion response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "doc_123",
                    "version_id": "ver_001",
                    "job_id": "job_456",
                    "status": "indexing",
                    "request_id": "req_demo",
                }
            ]
        }
    )

    document_id: str
    version_id: str
    job_id: str
    status: DocumentStatus = DocumentStatus.INDEXING
    request_id: str


class DocumentSummary(BaseModel):
    """Safe document metadata for list responses."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    title: str
    content_hash: str
    active_version_id: str | None
    status: DocumentStatus
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Bounded document listing response."""

    items: list[DocumentSummary]
    next_cursor: str | None


class DocumentDetailResponse(DocumentSummary):
    """Document detail response with version information."""

    available_version_ids: list[str]


class DeleteDocumentResponse(BaseModel):
    """Accepted document deletion response."""

    document_id: str
    status: str = "deleted"
    request_id: str


class JobResponse(BaseModel):
    """Asynchronous ingestion job status."""

    job_id: str
    document_id: str
    status: JobStatus
    progress_percent: int = Field(ge=0, le=100)
    error_code: str | None
    request_id: str


class SourceResponse(BaseModel):
    """Evidence source returned to a caller."""

    source_id: str
    document_id: str
    version_id: str
    page: int | None = Field(default=None, ge=1)
    title: str | None
    snippet: str
    score: float | None


class RetrievalInfo(BaseModel):
    """Debug-safe retrieval counts and selected strategy."""

    mode: RetrievalMode
    dense_candidates: int = Field(ge=0)
    sparse_candidates: int = Field(ge=0)
    rrf_candidates: int = Field(ge=0)
    reranked_candidates: int = Field(ge=0)


class LatencyBreakdown(BaseModel):
    """Stage-level latency measurements in milliseconds."""

    embedding_ms: float = Field(ge=0)
    search_ms: float = Field(ge=0)
    rerank_ms: float = Field(ge=0)
    llm_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)


class ModelInfo(BaseModel):
    """Model metadata; null means the LLM stage was skipped."""

    provider: str | None
    model: str | None


class OutputWarningResponse(BaseModel):
    """Structured output/evidence concern for human or policy review."""

    code: EvidenceWarningCode
    message: str
    values: list[str]


class QueryRequest(BaseModel):
    """Question and bounded retrieval controls."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
                    "retrieval_mode": "hybrid",
                    "top_k": 5,
                    "include_debug": False,
                }
            ]
        }
    )

    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = Field(default=5, ge=1, le=20)
    include_debug: bool = False
    tenant_id: str | None = Field(default=None, max_length=128)
    acl_tags: list[str] = Field(default_factory=list, max_length=50)


class QueryResponse(BaseModel):
    """Answer or explicit no-answer response contract."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "decision": "no_answer",
                    "answer": None,
                    "no_answer_reason": "NO_EVIDENCE",
                    "sources": [],
                    "retrieval": {
                        "mode": "hybrid",
                        "dense_candidates": 30,
                        "sparse_candidates": 30,
                        "rrf_candidates": 20,
                        "reranked_candidates": 5,
                    },
                    "model": {"provider": None, "model": None},
                    "warnings": [],
                    "latency": {
                        "embedding_ms": 12.4,
                        "search_ms": 18.1,
                        "rerank_ms": 38.2,
                        "llm_ms": 0,
                        "total_ms": 70.1,
                    },
                    "request_id": "req_demo",
                }
            ]
        }
    )

    decision: Decision
    answer: str | None
    no_answer_reason: NoAnswerReason | None
    sources: list[SourceResponse]
    retrieval: RetrievalInfo
    model: ModelInfo
    warnings: list[OutputWarningResponse] = Field(default_factory=list)
    latency: LatencyBreakdown
    request_id: str

    @model_validator(mode="after")
    def validate_decision_fields(self) -> "QueryResponse":
        """Keep answer and no-answer fields mutually consistent."""

        if self.decision is Decision.ANSWERED:
            if not self.answer or self.no_answer_reason is not None:
                raise ValueError("answered responses require answer and no reason")
        elif self.answer is not None or self.no_answer_reason is None:
            raise ValueError("no-answer responses require a reason and no answer")
        return self


class SearchRequest(BaseModel):
    """Evidence-only search request for retrieval debugging."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "Qdrant ne işe yarar?",
                    "retrieval_mode": "hybrid",
                    "top_k": 10,
                }
            ]
        }
    )

    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = Field(default=10, ge=1, le=50)
    tenant_id: str | None = Field(default=None, max_length=128)
    acl_tags: list[str] = Field(default_factory=list, max_length=50)


class SearchResponse(BaseModel):
    """Retrieval candidates without LLM generation."""

    sources: list[SourceResponse]
    retrieval: RetrievalInfo
    latency: LatencyBreakdown
    request_id: str
