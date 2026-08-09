"""Answer-generation query contract routes."""

from fastapi import APIRouter, Request, status

from ..errors import openapi_error_responses
from ...observability.request_id import get_request_id
from ._not_ready import feature_not_ready
from .contracts import (
    LatencyBreakdown,
    ModelInfo,
    OutputWarningResponse,
    QueryRequest,
    QueryResponse,
    NoAnswerInfo,
    RetrievalInfo,
    RetrievalDebugCandidateResponse,
    RetrievalDebugResponse,
    SourceResponse,
)

router = APIRouter(prefix="/queries", tags=["query"])
legacy_router = APIRouter(prefix="/query", tags=["query"])


@legacy_router.post(
    "",
    response_model=QueryResponse,
    include_in_schema=True,
    responses={
        status.HTTP_200_OK: {"model": QueryResponse},
        **openapi_error_responses(),
    },
)
@router.post(
    "",
    response_model=QueryResponse,
    responses={
        status.HTTP_200_OK: {"model": QueryResponse},
        **openapi_error_responses(),
    },
)
async def query(http_request: Request, request: QueryRequest) -> QueryResponse:
    """Answer from filtered evidence or return a structured no-answer."""

    query_service = getattr(http_request.app.state, "query_service", None)
    if query_service is None:
        feature_not_ready("Query")
    result = await query_service.execute(
        question=request.question,
        mode=request.retrieval_mode,
        top_k=request.top_k,
        document_ids=request.document_ids,
        tenant_id=request.tenant_id or "default",
        acl_tags=tuple(request.acl_tags or ["public"]),
    )
    return QueryResponse(
        decision=result.decision,
        answer=result.answer,
        no_answer_reason=result.no_answer_reason,
        no_answer=(
            NoAnswerInfo(
                reason_code=result.no_answer_reason,
                message=(
                    "Sufficient evidence was not found; the LLM was skipped."
                ),
            )
            if result.no_answer_reason is not None
            else None
        ),
        sources=[
            SourceResponse(
                source_id=candidate.source_id,
                document_id=candidate.document_id,
                version_id=candidate.version_id,
                chunk_id=candidate.source_id,
                parent_id=candidate.parent_id,
                page=candidate.page_start,
                page_start=candidate.page_start,
                page_end=candidate.page_end,
                title=candidate.title or None,
                snippet=candidate.text[:500],
                excerpt=candidate.text[:500],
                score=(
                    candidate.rerank_score
                    if candidate.rerank_score is not None
                    else candidate.score
                ),
                dense_score=candidate.dense_score,
                sparse_score=candidate.sparse_score,
                rerank_score=candidate.rerank_score,
            )
            for candidate in result.sources
        ],
        retrieval=RetrievalInfo(
            mode=request.retrieval_mode,
            dense_candidates=result.retrieval.dense_candidates,
            sparse_candidates=result.retrieval.sparse_candidates,
            rrf_candidates=result.retrieval.rrf_candidates,
            reranked_candidates=result.retrieval.reranked_candidates,
        ),
        model=ModelInfo(provider=result.provider, model=result.model),
        warnings=[
            OutputWarningResponse(
                code=warning.code,
                message=warning.message,
                values=list(warning.values),
            )
            for warning in result.warnings
        ],
        latency=LatencyBreakdown(
            embedding_ms=result.retrieval.embedding_ms,
            search_ms=result.retrieval.search_ms,
            rerank_ms=result.retrieval.rerank_ms,
            llm_ms=result.llm_ms,
            total_ms=result.total_ms,
        ),
        debug=(
            RetrievalDebugResponse(
                candidates=[
                    RetrievalDebugCandidateResponse(
                        source_id=item.source_id,
                        retrieval_rank=item.retrieval_rank,
                        rerank_rank=item.rerank_rank,
                        dense_rank=item.dense_rank,
                        sparse_rank=item.sparse_rank,
                        dense_score=item.dense_score,
                        sparse_score=item.sparse_score,
                        fused_score=item.fused_score,
                        rerank_score=item.rerank_score,
                        matched_terms=list(item.matched_terms),
                    )
                    for item in result.retrieval.debug_candidates
                ]
            )
            if request.include_debug
            else None
        ),
        request_id=get_request_id(),
    )
