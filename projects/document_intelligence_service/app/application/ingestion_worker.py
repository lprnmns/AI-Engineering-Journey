"""Asynchronous ingestion worker orchestration."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from ..domain.entities import DocumentStatus, JobStatus, StageStatus
from ..domain.errors import ErrorCode, ServiceError
from ..domain.chunks import ChildChunk, ParentSection, SectionMarker
from ..domain.ingestion import (
    JobSnapshot,
    PreparedIngestion,
    StageData,
    StageEvent,
    compute_version_id,
)
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
        section_markers: tuple[SectionMarker, ...] = (),
    ) -> None:
        self._registry = registry
        self._chunker = chunker
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._vector_store = vector_store
        self._language = language
        self._section_markers = section_markers

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

        current = await self._set_progress(snapshot, JobStatus.RUNNING, 1)
        active_stage: str | None = None
        stage_started: datetime | None = None
        try:
            current, stage_started = await self._begin_stage(
                current,
                "validate",
                {"bytes": prepared.upload.size_bytes, "pages": prepared.pdf.page_count},
            )
            active_stage = "validate"
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"bytes": prepared.upload.size_bytes, "pages": prepared.pdf.page_count},
                decision="accepted",
            )
            active_stage = None
            current = await self._set_progress(current, JobStatus.RUNNING, 10)

            current, stage_started = await self._begin_stage(
                current,
                "inspect",
                {"bytes": prepared.upload.size_bytes},
            )
            active_stage = "inspect"
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"pages": prepared.pdf.page_count},
                decision="selectable_text_check_pending",
            )
            active_stage = None

            # Parsing, model inference and the Qdrant client are synchronous
            # adapters. Running them directly here would block the ASGI event
            # loop even though this orchestration method is async.
            current, stage_started = await self._begin_stage(
                current,
                "extract_and_chunk",
                {"pages": prepared.pdf.page_count},
            )
            active_stage = "extract_and_chunk"
            parents, chunks = await asyncio.to_thread(self._build_chunks, prepared)
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"parents": len(parents), "children": len(chunks)},
                decision="indexable_text_found",
            )
            active_stage = None
            current = await self._set_progress(current, JobStatus.RUNNING, 35)
            texts = tuple(f"{chunk.title}\n{chunk.text}" for chunk in chunks)

            current, stage_started = await self._begin_stage(
                current,
                "embed_dense",
                {"chunks": len(chunks)},
            )
            active_stage = "embed_dense"
            dense_vectors = await asyncio.to_thread(
                self._dense_embedder.embed_documents,
                texts,
            )
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={
                    "vectors": len(dense_vectors),
                    "dimension": self._dense_embedder.dimension,
                },
                decision="dimension_verified",
            )
            active_stage = None

            current, stage_started = await self._begin_stage(
                current,
                "embed_sparse",
                {"chunks": len(chunks)},
            )
            active_stage = "embed_sparse"
            sparse_vectors = await asyncio.to_thread(
                self._sparse_embedder.embed_documents,
                texts,
            )
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"vectors": len(sparse_vectors)},
                decision="sparse_terms_encoded",
            )
            active_stage = None
            current = await self._set_progress(current, JobStatus.RUNNING, 65)

            current, stage_started = await self._begin_stage(
                current,
                "stage_qdrant",
                {"chunks": len(chunks)},
            )
            active_stage = "stage_qdrant"
            await asyncio.to_thread(
                self._vector_store.stage_version,
                chunks=chunks,
                dense_vectors=dense_vectors,
                sparse_vectors=sparse_vectors,
                pipeline_fingerprint=prepared.pipeline_fingerprint,
                language=self._language,
            )
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"points": len(chunks), "active": 0},
                decision="staged_inactive",
            )
            active_stage = None
            current = await self._set_progress(current, JobStatus.RUNNING, 75)

            current, stage_started = await self._begin_stage(
                current,
                "verify",
                {"expected_points": len(chunks)},
            )
            active_stage = "verify"
            verification = await asyncio.to_thread(
                self._vector_store.verify_version,
                document_id=self._document_id(prepared),
                version_id=self._version_id(prepared),
                expected_chunk_count=len(chunks),
            )
            if not verification.is_valid:
                raise ServiceError(
                    code=ErrorCode.INGESTION_FAILED,
                    message="Staged vector version failed verification",
                )
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={
                    "expected_points": verification.expected_chunk_count,
                    "actual_points": verification.actual_chunk_count,
                    "inactive_points": verification.inactive_chunk_count,
                },
                decision="schema_and_count_verified",
            )
            active_stage = None
            current = await self._set_progress(current, JobStatus.RUNNING, 90)

            current, stage_started = await self._begin_stage(
                current,
                "activate",
                {"version_id": verification.version_id},
            )
            active_stage = "activate"
            await asyncio.to_thread(
                self._vector_store.activate_version,
                document_id=verification.document_id,
                version_id=verification.version_id,
                verification=verification,
            )
            await self._registry.set_document_status(
                document_id=verification.document_id,
                version_id=verification.version_id,
                status=DocumentStatus.ACTIVE,
            )
            current = await self._finish_stage(
                current,
                active_stage,
                stage_started,
                outputs={"points": verification.actual_chunk_count, "active": 1},
                decision="active_version_published",
            )
            active_stage = None
        except ServiceError as error:
            if active_stage is not None and stage_started is not None:
                current = await self._finish_stage(
                    current,
                    active_stage,
                    stage_started,
                    status=StageStatus.FAILED,
                    decision="rejected",
                    error_code=error.code,
                    error_message=error.message,
                )
            return await self._fail(current, error.code, error.message, prepared)
        except Exception as error:
            message = str(error) or "Ingestion worker failed"
            if active_stage is not None and stage_started is not None:
                current = await self._finish_stage(
                    current,
                    active_stage,
                    stage_started,
                    status=StageStatus.FAILED,
                    decision="rejected",
                    error_code=ErrorCode.INGESTION_FAILED,
                    error_message=message,
                )
            return await self._fail(
                current,
                ErrorCode.INGESTION_FAILED,
                message,
                prepared,
            )

        current = await self._set_progress(current, JobStatus.SUCCEEDED, 100)
        return await self._finish_stage(
            current,
            "complete",
            datetime.now(timezone.utc),
            outputs={"points": current.point_count or 0},
            decision="succeeded",
        )

    def _build_chunks(
        self,
        prepared: PreparedIngestion,
    ) -> tuple[tuple[ParentSection, ...], tuple[ChildChunk, ...]]:
        parents, chunks = self._chunker.build_chunks(
            content=prepared.content,
            document_id=self._document_id(prepared),
            version_id=self._version_id(prepared),
            source=prepared.upload.filename,
            markers=self._section_markers,
        )
        if not chunks:
            raise ServiceError(
                code=ErrorCode.DOCUMENT_PARSE_FAILED,
                message="PDF contains no indexable text",
            )
        return parents, chunks

    async def _begin_stage(
        self,
        previous: JobSnapshot,
        name: str,
        inputs: StageData,
    ) -> tuple[JobSnapshot, datetime]:
        """Persist a running stage so polling can show the live boundary."""

        started_at = datetime.now(timezone.utc)
        await self._registry.record_stage_event(
            previous.job_id,
            StageEvent(
                name=name,
                status=StageStatus.RUNNING,
                started_at=started_at,
                inputs=inputs,
            ),
        )
        refreshed = await self._registry.get_job(previous.job_id)
        return refreshed or previous, started_at

    async def _finish_stage(
        self,
        previous: JobSnapshot,
        name: str,
        started_at: datetime,
        *,
        status: StageStatus = StageStatus.SUCCEEDED,
        outputs: StageData | None = None,
        decision: str | None = None,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> JobSnapshot:
        """Persist a terminal stage event with a monotonic duration."""

        finished_at = datetime.now(timezone.utc)
        inputs = next(
            (
                event.inputs
                for event in previous.stages
                if event.name == name and event.inputs is not None
            ),
            None,
        )
        event = StageEvent(
            name=name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0.0, (finished_at - started_at).total_seconds() * 1000),
            inputs=inputs,
            outputs=outputs,
            decision=decision,
            error_code=error_code.value if error_code is not None else None,
            error_message=error_message,
        )
        await self._registry.record_stage_event(previous.job_id, event)
        refreshed = await self._registry.get_job(previous.job_id)
        return refreshed or previous

    @staticmethod
    def _document_id(prepared: PreparedIngestion) -> str:
        return f"doc_{prepared.upload.content_hash}"

    @staticmethod
    def _version_id(prepared: PreparedIngestion) -> str:
        """Reconstruct the deterministic version ID used by the registry."""

        return compute_version_id(
            prepared.upload.content_hash,
            prepared.pipeline_fingerprint,
        )

    async def _set_progress(
        self,
        previous: JobSnapshot,
        status: JobStatus,
        progress_percent: int,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> JobSnapshot:
        snapshot = replace(
            previous,
            status=status,
            progress_percent=progress_percent,
            error_code=error_code.value if error_code is not None else previous.error_code,
            error_message=error_message or previous.error_message,
        )
        await self._registry.update_job(snapshot)
        return snapshot

    async def _fail(
        self,
        previous: JobSnapshot,
        code: ErrorCode,
        message: str,
        prepared: PreparedIngestion | None = None,
    ) -> JobSnapshot:
        if prepared is not None:
            await self._registry.set_document_status(
                document_id=self._document_id(prepared),
                version_id=self._version_id(prepared),
                status=DocumentStatus.FAILED,
            )
        return await self._set_progress(
            previous,
            JobStatus.FAILED,
            previous.progress_percent,
            error_code=code,
            error_message=message,
        )
