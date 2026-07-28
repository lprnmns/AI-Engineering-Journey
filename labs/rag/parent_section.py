from __future__ import annotations

from labs.rag.chunking import ChunkSearchResult
from labs.rag.reranker import RerankedChunkResult
from labs.rag.sample_docs import Document


def parent_section_as_context_result(
    selected: RerankedChunkResult,
    documents_by_id: dict[str, Document],
) -> ChunkSearchResult:
    """Expand a selected child chunk into the full section used as LLM context."""
    try:
        document = documents_by_id[selected.doc_id]
    except KeyError as error:
        raise RuntimeError(f"selected section is missing: {selected.doc_id}") from error

    return ChunkSearchResult(
        chunk_id=f"{document.doc_id}_parent_section",
        doc_id=document.doc_id,
        title=document.title,
        text=document.text,
        source=document.source,
        chunk_index=0,
        score=selected.retrieval_score,
    )
