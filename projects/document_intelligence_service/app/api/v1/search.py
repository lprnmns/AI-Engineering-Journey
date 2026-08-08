"""Evidence-only retrieval contract routes."""

from fastapi import APIRouter, Request, status

from ..errors import openapi_error_responses
from ...observability.request_id import get_request_id
from ._not_ready import feature_not_ready
from .contracts import SearchRequest, SearchResponse
from .contracts import LatencyBreakdown, RetrievalInfo, SourceResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    responses={
        status.HTTP_200_OK: {"model": SearchResponse},
        **openapi_error_responses(),
    },
)
async def search(request: Request, payload: SearchRequest) -> SearchResponse:
    """Return retrieval evidence without calling the LLM."""

    retrieval_service = getattr(request.app.state, "retrieval_service", None)
    if retrieval_service is None:
        feature_not_ready("Search")
    if payload.tenant_id or payload.acl_tags:
        feature_not_ready("Tenant/ACL-filtered search")

    result = retrieval_service.search(
        question=payload.question,
        mode=payload.retrieval_mode,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )
    return SearchResponse(
        sources=[
            SourceResponse(
                source_id=candidate.source_id,
                document_id=candidate.document_id,
                version_id=candidate.version_id,
                page=candidate.page_start,
                title=candidate.title or None,
                snippet=candidate.text[:500],
                score=candidate.score,
            )
            for candidate in result.candidates
        ],
        retrieval=RetrievalInfo(
            mode=payload.retrieval_mode,
            dense_candidates=result.dense_candidates,
            sparse_candidates=result.sparse_candidates,
            rrf_candidates=result.rrf_candidates,
            reranked_candidates=result.reranked_candidates,
        ),
        latency=LatencyBreakdown(
            embedding_ms=result.embedding_ms,
            search_ms=result.search_ms,
            rerank_ms=result.rerank_ms,
            llm_ms=0,
            total_ms=result.embedding_ms + result.search_ms + result.rerank_ms,
        ),
        request_id=get_request_id(),
    )
