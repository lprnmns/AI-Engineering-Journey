"""Answer-generation query contract routes."""

from fastapi import APIRouter, status

from ..errors import openapi_error_responses
from ._not_ready import feature_not_ready
from .contracts import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post(
    "",
    response_model=QueryResponse,
    responses={
        status.HTTP_200_OK: {"model": QueryResponse},
        **openapi_error_responses(),
    },
)
async def query(request: QueryRequest) -> QueryResponse:
    """Answer from filtered evidence or return a structured no-answer."""

    del request
    feature_not_ready("Query")
