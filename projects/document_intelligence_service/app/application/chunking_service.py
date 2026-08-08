"""Page-aware parsing and chunking use case."""

from ..domain.chunks import (
    ChildChunk,
    ParentSection,
    SectionMarker,
    chunk_parent_section,
    sectionize_pages,
)
from ..domain.ingestion import PipelineConfig
from .ports import PageTextExtractor


class DocumentChunkingService:
    """Orchestrate extraction, sectioning and child chunk creation."""

    def __init__(
        self,
        *,
        extractor: PageTextExtractor,
        pipeline_config: PipelineConfig,
    ) -> None:
        self._extractor = extractor
        self._pipeline_config = pipeline_config

    def build_chunks(
        self,
        *,
        content: bytes,
        document_id: str,
        version_id: str,
        source: str,
        markers: tuple[SectionMarker, ...] = (),
    ) -> tuple[tuple[ParentSection, ...], tuple[ChildChunk, ...]]:
        """Return parent context and retrieval children with page metadata."""

        pages = self._extractor.extract(content)
        parents = sectionize_pages(
            pages=pages,
            document_id=document_id,
            version_id=version_id,
            source=source,
            markers=markers,
        )
        children = tuple(
            child
            for parent in parents
            for child in chunk_parent_section(
                parent,
                max_sentences=self._pipeline_config.chunk_size_sentences,
                overlap_sentences=self._pipeline_config.chunk_overlap_sentences,
            )
        )
        return parents, children
