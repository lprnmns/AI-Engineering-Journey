"""Framework-independent ingestion identities and validation rules."""

from dataclasses import dataclass
import hashlib
import json

from .errors import ErrorCode, ServiceError
from .entities import DocumentStatus, JobStatus


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    """Safety limits applied before expensive PDF processing."""

    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 200

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0 or self.max_pdf_pages <= 0:
            raise ValueError("ingestion limits must be positive")


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Versioned inputs that affect generated chunks and vectors."""

    parser: str = "pypdf"
    parser_version: str = "1"
    normalizer: str = "unicode_whitespace_v1"
    chunker: str = "section_aware_v1"
    chunker_version: str = "1"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    vector_schema_version: str = "1"

    def canonical_dict(self) -> dict[str, str]:
        """Return deterministic, explicit fingerprint inputs."""

        return {
            "parser": self.parser,
            "parser_version": self.parser_version,
            "normalizer": self.normalizer,
            "chunker": self.chunker,
            "chunker_version": self.chunker_version,
            "embedding_model": self.embedding_model,
            "reranker_model": self.reranker_model,
            "vector_schema_version": self.vector_schema_version,
        }


@dataclass(frozen=True, slots=True)
class UploadMetadata:
    """Validated metadata that is safe to pass into parsing."""

    filename: str
    content_type: str
    size_bytes: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class PdfInspection:
    """Structural facts collected from a valid PDF."""

    page_count: int


@dataclass(frozen=True, slots=True)
class PreparedIngestion:
    """Identity and structural metadata before persistence/indexing."""

    content: bytes
    upload: UploadMetadata
    pdf: PdfInspection
    pipeline_fingerprint: str


@dataclass(frozen=True, slots=True)
class IngestionReceipt:
    """Stable identifiers returned when an ingestion is accepted."""

    document_id: str
    version_id: str
    job_id: str
    status: DocumentStatus


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    """Publicly mappable state of an accepted ingestion job."""

    job_id: str
    document_id: str
    status: JobStatus
    progress_percent: int
    error_code: str | None


def compute_content_hash(content: bytes) -> str:
    """Return the collision-resistant identity of exact input bytes."""

    return hashlib.sha256(content).hexdigest()


def compute_pipeline_fingerprint(config: PipelineConfig) -> str:
    """Return a deterministic identity for all vector-producing settings."""

    canonical = json.dumps(
        config.canonical_dict(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_upload_metadata(
    *,
    content: bytes,
    filename: str,
    content_type: str | None,
    limits: IngestionLimits,
) -> UploadMetadata:
    """Validate cheap upload properties before parsing or embedding."""

    if len(content) > limits.max_upload_bytes:
        raise ServiceError(
            code=ErrorCode.UPLOAD_TOO_LARGE,
            message="PDF upload exceeds the configured size limit",
        )

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type != "application/pdf":
        raise ServiceError(
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message="Only application/pdf uploads are supported",
        )

    if not content.startswith(b"%PDF"):
        raise ServiceError(
            code=ErrorCode.DOCUMENT_PARSE_FAILED,
            message="Uploaded bytes do not have a valid PDF signature",
        )

    safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not safe_filename.lower().endswith(".pdf"):
        raise ServiceError(
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            message="PDF filename must end with .pdf",
        )

    return UploadMetadata(
        filename=safe_filename,
        content_type=normalized_content_type,
        size_bytes=len(content),
        content_hash=compute_content_hash(content),
    )
