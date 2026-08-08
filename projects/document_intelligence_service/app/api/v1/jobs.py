"""Asynchronous ingestion job contract routes."""

from typing import Annotated

from fastapi import APIRouter, Path

from ..errors import openapi_error_responses
from ._not_ready import feature_not_ready
from .contracts import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    responses={**openapi_error_responses()},
)
async def get_job(
    job_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> JobResponse:
    """Return asynchronous ingestion progress."""

    del job_id
    feature_not_ready("Job status")
