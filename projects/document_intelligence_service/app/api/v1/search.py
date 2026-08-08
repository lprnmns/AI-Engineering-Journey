"""Evidence-only retrieval contract routes."""

from fastapi import APIRouter, status

from ..errors import openapi_error_responses
from ._not_ready import feature_not_ready
from .contracts import SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    responses={
        status.HTTP_200_OK: {"model": SearchResponse},
        **openapi_error_responses(),
    },
)
async def search(request: SearchRequest) -> SearchResponse:
    """Return retrieval evidence without calling the LLM."""

    del request
    feature_not_ready("Search")
