"""Environment-backed service settings."""

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Validated runtime configuration loaded from DIS_* variables."""

    model_config = SettingsConfigDict(
        env_prefix="DIS_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    service_name: str = "document-intelligence-service"
    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:6333")
    qdrant_collection: str = "document_chunks_v2_bm25"
    ollama_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    dependency_timeout_seconds: float = Field(default=1.0, gt=0, le=10)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    ingestion_registry_backend: Literal["memory", "sqlite"] = "memory"
    ingestion_database_path: str = "data/ingestions.sqlite3"
    embedded_worker: bool = True
    # Once the real adapters are wired, model loading belongs to the
    # application lifecycle rather than the first user request. Tests can
    # still disable this explicitly when they inject fakes.
    preload_models: bool = True
    worker_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    worker_stale_after_seconds: float = Field(default=300.0, gt=0, le=3600)
    bm25_state_path: str = "data/bm25_state.json"
    evaluation_artifact_dir: str = "projects/document_intelligence_service/eval/results/api_runs"
    section_marker_profile: Literal["none", "mentor_program_v1"] = "none"
    dense_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    sparse_model: str = "bm25_qdrant_idf_v2"
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    chunk_size_sentences: int = Field(default=3, ge=1, le=20)
    chunk_overlap_sentences: int = Field(default=1, ge=0, le=19)
    retrieval_candidate_k: int = Field(default=30, ge=1, le=50)
    retrieval_fusion_k: int = Field(default=20, ge=1, le=50)
    retrieval_rerank_k: int = Field(default=5, ge=1, le=20)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    log_level: str = "INFO"
    log_query_text: bool = False
    reranker_enabled: bool = False
    llm_model: str = "gemma3:4b"
    llm_timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    llm_max_output_tokens: int = Field(default=256, gt=0, le=1024)
    answerability_min_dense_score: float = Field(default=0.338, ge=0, le=1)
    answerability_min_sparse_score: float = Field(default=0.1, ge=0)
    answerability_min_rerank_score: float = -5.0
    answerability_min_margin: float = 0.0
    answerability_min_coverage: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        """Reject an impossible overlapping sentence window early."""

        if self.chunk_overlap_sentences >= self.chunk_size_sentences:
            raise ValueError(
                "chunk_overlap_sentences must be smaller than chunk_size_sentences"
            )
        return self
