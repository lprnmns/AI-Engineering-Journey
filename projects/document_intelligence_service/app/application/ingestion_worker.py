"""Asynchronous ingestion worker orchestration."""

from ..domain.entities import JobStatus
from ..domain.errors import ErrorCode, ServiceError
from ..domain.chunks import ChildChunk
from ..domain.ingestion import JobSnapshot, PreparedIngestion
from .chunking_service import DocumentChunkingService
from .ports import (
    ChunkVectorStore,
    DenseEmbedder,
    IngestionRegistry,
    SparseEmbedder,
)


class IngestionWorker:
    """Run one accepted ingestion through stage, verify and activate gates."""

    def __init__(
        self,
        *,
        registry: IngestionRegistry,
        chunker: DocumentChunkingService,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
        vector_store: ChunkVectorStore,
        language: str = "tr",
    ) -> None:
        self._registry = registry
        self._chunker = chunker
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._vector_store = vector_store
        self._language = language

    async def run_job(self, job_id: str) -> JobSnapshot:
        """Process one job and persist a terminal success/failure snapshot."""

        snapshot = await self._registry.get_job(job_id)
        if snapshot is None:
            raise ServiceError(
                code=ErrorCode.JOB_NOT_FOUND,
                message="Job was not found",
            )
        if snapshot.status is JobStatus.SUCCEEDED:
            return snapshot

        prepared = await self._registry.get_staged_ingestion(job_id)
        if prepared is None:
            return await self._fail(
                snapshot,
                ErrorCode.DOCUMENT_PARSE_FAILED,
                "Staged ingestion content was not found",
            )

        current = await self._set_progress(snapshot, JobStatus.RUNNING, 10)
        try:
            chunks = self._build_chunks(prepared)
            current = await self._set_progress(current, JobStatus.RUNNING, 35)
            texts = tuple(f"{chunk.title}\n{chunk.text}" for chunk in chunks)
            dense_vectors = self._dense_embedder.embed_documents(texts)
            sparse_vectors = self._sparse_embedder.embed_documents(texts)
            current = await self._set_progress(current, JobStatus.RUNNING, 65)

            self._vector_store.stage_version(
                chunks=chunks,
                dense_vectors=dense_vectors,
                sparse_vectors=sparse_vectors,
                pipeline_fingerprint=prepared.pipeline_fingerprint,
                language=self._language,
            )
            current = await self._set_progress(current, JobStatus.RUNNING, 80)
            verification = self._vector_store.verify_version(
                document_id=self._document_id(prepared),
                version_id=self._version_id(prepared),
                expected_chunk_count=len(chunks),
            )
            if not verification.is_valid:
                raise ServiceError(
                    code=ErrorCode.INGESTION_FAILED,
                    message="Staged vector version failed verification",
                )
            self._vector_store.activate_version(
                document_id=verification.document_id,
                version_id=verification.version_id,
                verification=verification,
            )
        except ServiceError as error:
            return await self._fail(current, error.code, error.message)
        except Exception:
            return await self._fail(
                current,
                ErrorCode.INGESTION_FAILED,
                "Ingestion worker failed",
            )

        return await self._set_progress(current, JobStatus.SUCCEEDED, 100)

    def _build_chunks(self, prepared: PreparedIngestion) -> tuple[ChildChunk, ...]:
        _, chunks = self._chunker.build_chunks(
            content=prepared.content,
            document_id=self._document_id(prepared),
            version_id=self._version_id(prepared),
            source=prepared.upload.filename,
        )
        if not chunks:
            raise ServiceError(
                code=ErrorCode.DOCUMENT_PARSE_FAILED,
                message="PDF contains no indexable text",
            )
        return chunks

    @staticmethod
    def _document_id(prepared: PreparedIngestion) -> str:
        return f"doc_{prepared.upload.content_hash}"

    @staticmethod
    def _version_id(prepared: PreparedIngestion) -> str:
        """Reconstruct the deterministic version ID used by the registry."""

        import hashlib

        digest = hashlib.sha256(
            f"{prepared.upload.content_hash}:{prepared.pipeline_fingerprint}".encode(
                "ascii"
            )
        ).hexdigest()
        return f"ver_{digest}"

    async def _set_progress(
        self,
        previous: JobSnapshot,
        status: JobStatus,
        progress_percent: int,
        error_code: ErrorCode | None = None,
    ) -> JobSnapshot:
        snapshot = JobSnapshot(
            job_id=previous.job_id,
            document_id=previous.document_id,
            status=status,
            progress_percent=progress_percent,
            error_code=error_code.value if error_code is not None else None,
        )
        await self._registry.update_job(snapshot)
        return snapshot

    async def _fail(
        self,
        previous: JobSnapshot,
        code: ErrorCode,
        message: str,
    ) -> JobSnapshot:
        del message
        return await self._set_progress(
            previous,
            JobStatus.FAILED,
            previous.progress_percent,
            error_code=code,
        )
