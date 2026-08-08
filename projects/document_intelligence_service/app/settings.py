"""Environment-backed service settings."""

from pydantic import AnyHttpUrl, Field
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
    ollama_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")
    dependency_timeout_seconds: float = Field(default=1.0, gt=0, le=10)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    ingestion_registry_backend: Literal["memory", "sqlite"] = "memory"
    ingestion_database_path: str = "data/ingestions.sqlite3"
    reranker_enabled: bool = False
