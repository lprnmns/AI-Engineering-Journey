"""Restart-safe SQLite adapter for ingestion identities, jobs and staged PDFs."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from ...domain.entities import DocumentStatus, JobStatus, StageStatus
from ...domain.errors import ErrorCode, ServiceError
from ...domain.ingestion import (
    DocumentPage,
    DocumentSnapshot,
    IngestionReceipt,
    JobSnapshot,
    PdfInspection,
    PreparedIngestion,
    StageEvent,
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

    async def list_documents(self, limit: int, cursor: str | None) -> DocumentPage:
        """Return stable cursor pagination over logical documents."""

        if limit <= 0 or limit > 100:
            raise ValueError("document limit must be between 1 and 100")
        return await asyncio.to_thread(self._list_documents_sync, limit, cursor)

    async def get_document(self, document_id: str) -> DocumentSnapshot | None:
        """Return one logical document and all known versions."""

        return await asyncio.to_thread(self._get_document_sync, document_id)

    async def delete_document(self, document_id: str) -> None:
        """Mark all versions deleted unless an ingestion is still running."""

        await asyncio.to_thread(self._delete_document_sync, document_id)

    async def update_job(self, snapshot: JobSnapshot) -> None:
        """Persist one worker progress transition."""

        await asyncio.to_thread(self._update_job_sync, snapshot)

    async def record_stage_event(self, job_id: str, event: StageEvent) -> None:
        """Append one stage transition and update the job summary."""

        await asyncio.to_thread(self._record_stage_event_sync, job_id, event)

    async def set_document_status(
        self,
        *,
        document_id: str,
        version_id: str,
        status: DocumentStatus,
    ) -> None:
        """Persist a version lifecycle transition independently from the job."""

        await asyncio.to_thread(
            self._set_document_status_sync,
            document_id,
            version_id,
            status,
        )

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
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    acl_tags_json TEXT NOT NULL DEFAULT '["public"]',
                    created_at TEXT NOT NULL,
                    content BLOB NOT NULL,
                    document_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL,
                    error_code TEXT,
                    current_stage TEXT,
                    point_count INTEGER,
                    error_message TEXT,
                    failed_stage TEXT,
                    PRIMARY KEY (tenant_id, content_hash, pipeline_fingerprint)
                );

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    content_hash TEXT NOT NULL,
                    pipeline_fingerprint TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ingestions_job_id
                    ON ingestions(job_id);

                CREATE TABLE IF NOT EXISTS ingestion_stage_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_ms REAL,
                    inputs_json TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    decision TEXT,
                    warnings_json TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_stage_events_job_id
                    ON ingestion_stage_events(job_id, event_id);
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
            for column, definition in (
                ("tenant_id", "TEXT NOT NULL DEFAULT 'default'"),
                ("acl_tags_json", "TEXT NOT NULL DEFAULT '[\"public\"]'"),
                (
                    "created_at",
                    "TEXT NOT NULL DEFAULT '1970-01-01T00:00:00+00:00'",
                ),
                ("current_stage", "TEXT"),
                ("point_count", "INTEGER"),
                ("error_message", "TEXT"),
                ("failed_stage", "TEXT"),
            ):
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE ingestions ADD COLUMN {column} {definition}"
                    )
            idempotency_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(idempotency_keys)")
            }
            if "tenant_id" not in idempotency_columns:
                connection.execute(
                    "ALTER TABLE idempotency_keys ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'"
                )
            self._migrate_tenant_scoped_primary_key(connection)

    @staticmethod
    def _migrate_tenant_scoped_primary_key(connection: sqlite3.Connection) -> None:
        """Rebuild pre-ACL databases whose identity key was tenant-blind."""

        primary_key_columns = [
            row["name"]
            for row in sorted(
                connection.execute("PRAGMA table_info(ingestions)").fetchall(),
                key=lambda row: row["pk"],
            )
            if row["pk"]
        ]
        expected = ["tenant_id", "content_hash", "pipeline_fingerprint"]
        if primary_key_columns == expected:
            return
        if primary_key_columns != ["content_hash", "pipeline_fingerprint"]:
            raise RuntimeError("unsupported ingestions primary key schema")

        connection.execute(
            """
            CREATE TABLE ingestions_v2 (
                content_hash TEXT NOT NULL,
                pipeline_fingerprint TEXT NOT NULL,
                document_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                job_id TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                page_count INTEGER NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'default',
                acl_tags_json TEXT NOT NULL DEFAULT '["public"]',
                created_at TEXT NOT NULL,
                content BLOB NOT NULL,
                document_status TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percent INTEGER NOT NULL,
                error_code TEXT,
                current_stage TEXT,
                point_count INTEGER,
                error_message TEXT,
                failed_stage TEXT,
                PRIMARY KEY (tenant_id, content_hash, pipeline_fingerprint)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ingestions_v2 (
                content_hash, pipeline_fingerprint, document_id, version_id,
                job_id, filename, content_type, size_bytes, page_count,
                tenant_id, acl_tags_json, created_at, content, document_status,
                status, progress_percent, error_code, current_stage, point_count,
                error_message, failed_stage
            )
            SELECT content_hash, pipeline_fingerprint, document_id, version_id,
                   job_id, filename, content_type, size_bytes, page_count,
                   tenant_id, acl_tags_json, created_at, content, document_status,
                   status, progress_percent, error_code, current_stage, point_count,
                   error_message, failed_stage
            FROM ingestions
            """
        )
        connection.execute("DROP TABLE ingestions")
        connection.execute("ALTER TABLE ingestions_v2 RENAME TO ingestions")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingestions_job_id ON ingestions(job_id)"
        )

    def _accept_sync(
        self,
        prepared: PreparedIngestion,
        idempotency_key: str | None,
    ) -> IngestionReceipt:
        identity = (
            prepared.upload.tenant_id,
            prepared.upload.content_hash,
            prepared.pipeline_fingerprint,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key is not None:
                key_row = connection.execute(
                    """
                    SELECT tenant_id, content_hash, pipeline_fingerprint
                    FROM idempotency_keys
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
                if key_row is not None:
                    previous_identity = (
                        key_row["tenant_id"],
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
                WHERE tenant_id = ? AND content_hash = ? AND pipeline_fingerprint = ?
                """,
                identity,
            ).fetchone()
            if existing is not None:
                if idempotency_key is not None:
                    connection.execute(
                        """
                        INSERT INTO idempotency_keys
                            (idempotency_key, tenant_id, content_hash, pipeline_fingerprint)
                        VALUES (?, ?, ?, ?)
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
                    tenant_id, acl_tags_json, created_at, content, document_status, status, progress_percent, error_code,
                    current_stage, point_count, error_message, failed_stage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prepared.upload.content_hash,
                    prepared.pipeline_fingerprint,
                    receipt.document_id,
                    receipt.version_id,
                    receipt.job_id,
                    prepared.upload.filename,
                    prepared.upload.content_type,
                    prepared.upload.size_bytes,
                    prepared.pdf.page_count,
                    prepared.upload.tenant_id,
                    json.dumps(list(prepared.upload.acl_tags), ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                    prepared.content,
                    receipt.status.value,
                    JobStatus.QUEUED.value,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            if idempotency_key is not None:
                connection.execute(
                    """
                    INSERT INTO idempotency_keys
                        (idempotency_key, tenant_id, content_hash, pipeline_fingerprint)
                    VALUES (?, ?, ?, ?)
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
            if row is None:
                return None
            return self._job_from_row(
                row,
                self._stage_events_sync(connection, job_id),
            )

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
                tenant_id=row["tenant_id"],
                acl_tags=tuple(json.loads(row["acl_tags_json"])),
            ),
            pdf=PdfInspection(page_count=row["page_count"]),
            pipeline_fingerprint=row["pipeline_fingerprint"],
        )

    def _list_documents_sync(
        self,
        limit: int,
        cursor: str | None,
    ) -> DocumentPage:
        offset = _parse_cursor(cursor)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ingestions
                ORDER BY created_at ASC, document_id ASC, version_id ASC
                """
            ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["document_id"], []).append(row)
        snapshots = sorted(
            (_snapshot_from_rows(items) for items in grouped.values()),
            key=lambda item: (item.created_at, item.document_id),
            reverse=True,
        )
        page = snapshots[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(snapshots) else None
        return DocumentPage(items=tuple(page), next_cursor=next_cursor)

    def _get_document_sync(self, document_id: str) -> DocumentSnapshot | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ingestions
                WHERE document_id = ?
                ORDER BY created_at ASC, version_id ASC
                """,
                (document_id,),
            ).fetchall()
        return _snapshot_from_rows(rows) if rows else None

    def _delete_document_sync(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT status FROM ingestions WHERE document_id = ?",
                (document_id,),
            ).fetchall()
            if not rows:
                raise ServiceError(
                    code=ErrorCode.DOCUMENT_NOT_FOUND,
                    message="Document was not found",
                )
            if any(
                JobStatus(row["status"]) in (JobStatus.QUEUED, JobStatus.RUNNING)
                for row in rows
            ):
                raise ServiceError(
                    code=ErrorCode.DOCUMENT_BUSY,
                    message="Document has an ingestion job in progress",
                )
            connection.execute(
                "UPDATE ingestions SET document_status = ? WHERE document_id = ?",
                (DocumentStatus.DELETED.value, document_id),
            )

    def _update_job_sync(self, snapshot: JobSnapshot) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestions
                SET status = ?, progress_percent = ?, error_code = ?,
                    current_stage = ?, point_count = ?, error_message = ?,
                    failed_stage = ?
                WHERE job_id = ?
                """,
                (
                    snapshot.status.value,
                    snapshot.progress_percent,
                    snapshot.error_code,
                    snapshot.current_stage,
                    snapshot.point_count,
                    snapshot.error_message,
                    snapshot.failed_stage,
                    snapshot.job_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown job: {snapshot.job_id}")

    def _record_stage_event_sync(self, job_id: str, event: StageEvent) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_stage_events (
                    job_id, stage_name, status, started_at, finished_at,
                    duration_ms, inputs_json, outputs_json, decision,
                    warnings_json, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    event.name,
                    event.status.value,
                    event.started_at.isoformat(),
                    event.finished_at.isoformat() if event.finished_at else None,
                    event.duration_ms,
                    json.dumps(event.inputs or {}, sort_keys=True),
                    json.dumps(event.outputs or {}, sort_keys=True),
                    event.decision,
                    json.dumps(list(event.warnings), ensure_ascii=False),
                    event.error_code,
                    event.error_message,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("stage event was not persisted")
            output_points = (event.outputs or {}).get("points")
            connection.execute(
                """
                UPDATE ingestions
                SET current_stage = ?,
                    point_count = COALESCE(?, point_count),
                    error_code = COALESCE(?, error_code),
                    error_message = COALESCE(?, error_message),
                    failed_stage = CASE WHEN ? = 'failed' THEN ? ELSE failed_stage END
                WHERE job_id = ?
                """,
                (
                    event.name,
                    int(output_points)
                    if isinstance(output_points, (int, float))
                    else None,
                    event.error_code,
                    event.error_message,
                    event.status.value,
                    event.name,
                    job_id,
                ),
            )

    @staticmethod
    def _stage_events_sync(
        connection: sqlite3.Connection,
        job_id: str,
    ) -> tuple[StageEvent, ...]:
        rows = connection.execute(
            """
            SELECT stage_name, status, started_at, finished_at, duration_ms,
                   inputs_json, outputs_json, decision, warnings_json,
                   error_code, error_message
            FROM ingestion_stage_events
            WHERE job_id = ?
            ORDER BY event_id
            """,
            (job_id,),
        ).fetchall()
        latest: dict[str, StageEvent] = {}
        for row in rows:
            latest[row["stage_name"]] = StageEvent(
                name=row["stage_name"],
                status=StageStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=(
                    datetime.fromisoformat(row["finished_at"])
                    if row["finished_at"]
                    else None
                ),
                duration_ms=row["duration_ms"],
                inputs=json.loads(row["inputs_json"]),
                outputs=json.loads(row["outputs_json"]),
                decision=row["decision"],
                warnings=tuple(json.loads(row["warnings_json"])),
                error_code=row["error_code"],
                error_message=row["error_message"],
            )
        return tuple(latest.values())

    def _set_document_status_sync(
        self,
        document_id: str,
        version_id: str,
        status: DocumentStatus,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ingestions
                SET document_status = ?
                WHERE document_id = ? AND version_id = ?
                """,
                (status.value, document_id, version_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown document version: {document_id}/{version_id}")

    def _receipt_for_identity(
        self,
        connection: sqlite3.Connection,
        identity: tuple[str, str, str],
    ) -> IngestionReceipt:
        row = connection.execute(
            """
            SELECT * FROM ingestions
            WHERE tenant_id = ? AND content_hash = ? AND pipeline_fingerprint = ?
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
    def _job_from_row(
        row: sqlite3.Row,
        stages: tuple[StageEvent, ...] = (),
    ) -> JobSnapshot:
        return JobSnapshot(
            job_id=row["job_id"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            progress_percent=row["progress_percent"],
            error_code=row["error_code"],
            current_stage=row["current_stage"],
            stages=stages,
            page_count=row["page_count"],
            point_count=row["point_count"],
            error_message=row["error_message"],
            failed_stage=row["failed_stage"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection


def _parse_cursor(cursor: str | None) -> int:
    """Parse the intentionally opaque offset cursor used by this adapter."""

    if cursor is None:
        return 0
    if not cursor.isdigit():
        raise ServiceError(
            code=ErrorCode.INVALID_REQUEST,
            message="Document cursor is invalid",
        )
    return int(cursor)


def _snapshot_from_rows(rows: list[sqlite3.Row]) -> DocumentSnapshot:
    """Build one public document read model from its stored versions."""

    ordered = sorted(
        rows,
        key=lambda row: (row["created_at"], row["version_id"]),
    )
    statuses = {DocumentStatus(row["document_status"]) for row in ordered}
    if DocumentStatus.ACTIVE in statuses:
        status = DocumentStatus.ACTIVE
    elif DocumentStatus.INDEXING in statuses:
        status = DocumentStatus.INDEXING
    elif DocumentStatus.FAILED in statuses:
        status = DocumentStatus.FAILED
    else:
        status = DocumentStatus.DELETED
    active_versions = [
        row for row in ordered
        if DocumentStatus(row["document_status"]) is DocumentStatus.ACTIVE
    ]
    latest = ordered[-1]
    return DocumentSnapshot(
        document_id=latest["document_id"],
        title=latest["filename"],
        content_hash=latest["content_hash"],
        active_version_id=(
            active_versions[-1]["version_id"] if active_versions else None
        ),
        status=status,
        created_at=datetime.fromisoformat(ordered[0]["created_at"]),
        available_version_ids=tuple(row["version_id"] for row in ordered),
    )
