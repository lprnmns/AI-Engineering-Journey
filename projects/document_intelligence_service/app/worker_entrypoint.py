"""Standalone restart-safe ingestion worker process."""

import asyncio
import logging

from .application.ingestion_worker import IngestionWorker
from .main import build_ingestion_registry, build_ingestion_worker
from .observability.metrics import MetricsRegistry
from .settings import Settings

LOGGER = logging.getLogger("document_intelligence_service.worker")


async def run_worker(settings: Settings) -> None:
    """Poll durable jobs and resume queued, retryable or stale work."""

    registry = build_ingestion_registry(settings)
    worker: IngestionWorker = build_ingestion_worker(
        settings,
        registry=registry,
        metrics=MetricsRegistry(),
    )
    if settings.preload_models:
        worker.warmup()
    LOGGER.info("ingestion worker started")
    while True:
        job_ids = await registry.list_recoverable_jobs(
            limit=1,
            stale_after_seconds=settings.worker_stale_after_seconds,
        )
        if not job_ids:
            await asyncio.sleep(settings.worker_poll_interval_seconds)
            continue
        for job_id in job_ids:
            try:
                snapshot = await worker.run_job(job_id)
                LOGGER.info(
                    "ingestion job finished job_id=%s status=%s attempt=%s",
                    job_id,
                    snapshot.status.value,
                    snapshot.attempt_count,
                )
            except Exception:
                LOGGER.exception("ingestion job crashed job_id=%s", job_id)


def main() -> None:
    """Run the worker until the container receives a shutdown signal."""

    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker(Settings()))
    except KeyboardInterrupt:
        LOGGER.info("ingestion worker stopped")


if __name__ == "__main__":
    main()
