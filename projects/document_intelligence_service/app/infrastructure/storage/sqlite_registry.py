"""Restart-safe SQLite adapter for ingestion identities, jobs and staged PDFs."""

import asyncio
from pathlib import Path
import sqlite3

from ...domain.entities import DocumentStatus, JobStatus
from ...domain.errors import ErrorCode, ServiceError
from ...domain.ingestion import (
    IngestionReceipt,
    JobSnapshot,
    PdfInspection,
    PreparedIngestion,
    UploadMetadata,
    create_ingestion_receipt,
    normalize_idempotency_key,
)

class SqliteIngestionRegistry:
    """Persist accepted jobs and PDF bytes so another process can resume them."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        if str(self._database_path) != ":memory:":
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def database_path(self) -> Path:
        """Return the configured SQLite file path."""

        return self._database_path

    async def accept(
        self,
        prepared: PreparedIngestion,
        idempotency_key: str | None,
    ) -> IngestionReceipt:
        """Atomically accept or reuse one content/pipeline identity."""

        return await asyncio.to_thread(
            self._accept_sync,
            prepared,
            normalize_idempotency_key(idempotency_key),
        )

    async def get_job(self, job_id: str) -> JobSnapshot | None:
        """Read one durable job snapshot."""

        return await asyncio.to_thread(self._get_job_sync, job_id)

    async def get_staged_content(self, job_id: str) -> bytes | None:
        """Read the staged PDF bytes for a worker."""

        prepared = await self.get_staged_ingestion(job_id)
        return prepared.content if prepared is not None else None

    async def get_staged_ingestion(self, job_id: str) -> PreparedIngestion | None:
        """Read the complete staged identity required by the worker."""

        return await asyncio.to_thread(self._get_staged_sync, job_id)

    async def update_job(self, snapshot: JobSnapshot) -> None:
        """Persist one worker progress transition."""

        await asyncio.to_thread(self._update_job_sync, snapshot)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS ingestions (
                    content_hash TEXT NOT NULL,
                    pipeline_fingerprint TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    page_count INTEGER NOT NULL,
                    content BLOB NOT NULL,
                    document_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL,
                    error_code TEXT,
                    PRIMARY KEY (content_hash, pipeline_fingerprint)
                );

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    pipeline_fingerprint TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ingestions_job_id
                    ON ingestions(job_id);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(ingestions)")
            }
            if "document_status" not in columns:
                connection.execute(
                    """
                    ALTER TABLE ingestions
                    ADD COLUMN document_status TEXT NOT NULL DEFAULT 'indexing'
                    """
                )

    def _accept_sync(
        self,
        prepared: PreparedIngestion,
        idempotency_key: str | None,
    ) -> IngestionReceipt:
        identity = (
            prepared.upload.content_hash,
            prepared.pipeline_fingerprint,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key is not None:
                key_row = connection.execute(
                    """
                    SELECT content_hash, pipeline_fingerprint
                    FROM idempotency_keys
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
                if key_row is not None:
                    previous_identity = (
                        key_row["content_hash"],
                        key_row["pipeline_fingerprint"],
                    )
                    if previous_identity != identity:
                        raise ServiceError(
                            code=ErrorCode.INGESTION_CONFLICT,
                            message="Idempotency-Key was already used for another upload",
                        )
                    return self._receipt_for_identity(connection, identity)

            existing = connection.execute(
                """
                SELECT * FROM ingestions
                WHERE content_hash = ? AND pipeline_fingerprint = ?
                """,
                identity,
            ).fetchone()
            if existing is not None:
                if idempotency_key is not None:
                    connection.execute(
                        """
                        INSERT INTO idempotency_keys
                            (idempotency_key, content_hash, pipeline_fingerprint)
                        VALUES (?, ?, ?)
                        """,
                        (idempotency_key, *identity),
                    )
                return self._receipt_from_row(existing)

            receipt = create_ingestion_receipt(identity)
            connection.execute(
                """
                INSERT INTO ingestions (
                    content_hash, pipeline_fingerprint, document_id, version_id,
                    job_id, filename, content_type, size_bytes, page_count,
                    content, document_status, status, progress_percent, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    *identity,
                    receipt.document_id,
                    receipt.version_id,
                    receipt.job_id,
                    prepared.upload.filename,
                    prepared.upload.content_type,
                    prepared.upload.size_bytes,
                    prepared.pdf.page_count,
                    prepared.content,
                    receipt.status.value,
                    receipt.status.value,
                    0,
                    None,
                ),
            )
            if idempotency_key is not None:
                connection.execute(
                    """
                    INSERT INTO idempotency_keys
                        (idempotency_key, content_hash, pipeline_fingerprint)
                    VALUES (?, ?, ?)
                    """,
                    (idempotency_key, *identity),
                )
            return receipt

    def _get_job_sync(self, job_id: str) -> JobSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return self._job_from_row(row) if row is not None else None

    def _get_staged_sync(self, job_id: str) -> PreparedIngestion | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return PreparedIngestion(
            content=bytes(row["content"]),
            upload=UploadMetadata(
                filename=row["filename"],
                content_type=row["content_type"],
                size_bytes=row["size_bytes"],
                content_hash=row["content_hash"],
            ),
            pdf=PdfInspection(page_count=row["page_count"]),
            pipeline_fingerprint=row["pipeline_fingerprint"],
        )

    def _update_job_sync(self, snapshot: JobSnapshot) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestions
                SET status = ?, progress_percent = ?, error_code = ?
                WHERE job_id = ?
                """,
                (
                    snapshot.status.value,
                    snapshot.progress_percent,
                    snapshot.error_code,
                    snapshot.job_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown job: {snapshot.job_id}")

    def _receipt_for_identity(
        self,
        connection: sqlite3.Connection,
        identity: tuple[str, str],
    ) -> IngestionReceipt:
        row = connection.execute(
            """
            SELECT * FROM ingestions
            WHERE content_hash = ? AND pipeline_fingerprint = ?
            """,
            identity,
        ).fetchone()
        if row is None:
            raise RuntimeError("idempotency key points to a missing ingestion")
        return self._receipt_from_row(row)

    @staticmethod
    def _receipt_from_row(row: sqlite3.Row) -> IngestionReceipt:
        return IngestionReceipt(
            document_id=row["document_id"],
            version_id=row["version_id"],
            job_id=row["job_id"],
            status=DocumentStatus(row["document_status"]),
        )

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobSnapshot:
        return JobSnapshot(
            job_id=row["job_id"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            progress_percent=row["progress_percent"],
            error_code=row["error_code"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection
