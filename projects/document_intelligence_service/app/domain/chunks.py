"""Page-aware parent and child chunk domain objects."""

from dataclasses import dataclass
import hashlib
import re

from .errors import ErrorCode, ServiceError

_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class PageText:
    """Normalized selectable text belonging to one PDF page."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class SectionMarker:
    """Explicit heading rule for a known document family."""

    title: str
    marker: str


@dataclass(frozen=True, slots=True)
class ParentSection:
    """Larger source context retained around child chunks."""

    parent_id: str
    document_id: str
    version_id: str
    source: str
    title: str
    text: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ChildChunk:
    """Retrieval unit with enough metadata to restore parent evidence."""

    chunk_id: str
    parent_id: str
    document_id: str
    version_id: str
    source: str
    title: str
    text: str
    chunk_index: int
    page_start: int
    page_end: int
    token_count_estimate: int
    text_hash: str


def normalize_page_text(text: str) -> str:
    """Collapse PDF whitespace while preserving readable text order."""

    return " ".join(text.split())


def sectionize_pages(
    *,
    pages: tuple[PageText, ...],
    document_id: str,
    version_id: str,
    source: str,
    markers: tuple[SectionMarker, ...] = (),
) -> tuple[ParentSection, ...]:
    """Build ordered parent sections from pages and explicit markers.

    When no markers are configured, one document-level parent is retained. We
    do not guess headings from arbitrary typography at this stage.
    """

    non_empty_pages = tuple(page for page in pages if page.text)
    if not non_empty_pages:
        raise ServiceError(
            code=ErrorCode.DOCUMENT_PARSE_FAILED,
            message="PDF contains no selectable text",
        )

    joined_text = "\n".join(page.text for page in non_empty_pages)
    boundaries = _page_boundaries(non_empty_pages)
    if not markers:
        return (
            _make_parent(
                document_id=document_id,
                version_id=version_id,
                source=source,
                title=source,
                text=joined_text,
                start=0,
                end=len(joined_text),
                boundaries=boundaries,
                index=0,
            ),
        )

    positions: list[tuple[int, SectionMarker]] = []
    for marker in markers:
        position = joined_text.find(marker.marker)
        if position < 0:
            raise ServiceError(
                code=ErrorCode.DOCUMENT_PARSE_FAILED,
                message="Configured section marker was not found",
            )
        positions.append((position, marker))

    if positions != sorted(positions, key=lambda item: item[0]):
        raise ServiceError(
            code=ErrorCode.DOCUMENT_PARSE_FAILED,
            message="Configured section markers are out of order",
        )

    parents: list[ParentSection] = []
    for index, (start, marker) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(joined_text)
        parents.append(
            _make_parent(
                document_id=document_id,
                version_id=version_id,
                source=source,
                title=marker.title,
                text=joined_text[start:end].strip(),
                start=start,
                end=end,
                boundaries=boundaries,
                index=index,
            )
        )
    return tuple(parents)


def chunk_parent_section(
    parent: ParentSection,
    *,
    max_sentences: int = 3,
    overlap_sentences: int = 1,
) -> tuple[ChildChunk, ...]:
    """Create deterministic overlapping child chunks from one parent."""

    if max_sentences <= 0:
        raise ValueError("max_sentences must be greater than zero")
    if overlap_sentences < 0 or overlap_sentences >= max_sentences:
        raise ValueError("overlap_sentences must be smaller than max_sentences")

    sentences = _split_sentences(parent.text)
    if not sentences:
        return ()

    step = max_sentences - overlap_sentences
    chunks: list[ChildChunk] = []
    start = 0
    index = 1
    while start < len(sentences):
        text = " ".join(sentences[start : start + max_sentences])
        chunks.append(
            ChildChunk(
                chunk_id=f"{parent.parent_id}:child:{index:03d}",
                parent_id=parent.parent_id,
                document_id=parent.document_id,
                version_id=parent.version_id,
                source=parent.source,
                title=parent.title,
                text=text,
                chunk_index=index,
                page_start=parent.page_start,
                page_end=parent.page_end,
                token_count_estimate=len(text.split()),
                text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        if start + max_sentences >= len(sentences):
            break
        start += step
        index += 1
    return tuple(chunks)


def _split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []
    return [sentence.strip() for sentence in _SENTENCE_PATTERN.split(cleaned) if sentence.strip()]


def _page_boundaries(pages: tuple[PageText, ...]) -> tuple[tuple[int, int, int], ...]:
    boundaries: list[tuple[int, int, int]] = []
    cursor = 0
    for page in pages:
        end = cursor + len(page.text)
        boundaries.append((cursor, end, page.page_number))
        cursor = end + 1
    return tuple(boundaries)


def _page_for_offset(offset: int, boundaries: tuple[tuple[int, int, int], ...]) -> int:
    for start, end, page_number in boundaries:
        if start <= offset <= end:
            return page_number
    return boundaries[-1][2]


def _make_parent(
    *,
    document_id: str,
    version_id: str,
    source: str,
    title: str,
    text: str,
    start: int,
    end: int,
    boundaries: tuple[tuple[int, int, int], ...],
    index: int,
) -> ParentSection:
    return ParentSection(
        parent_id=f"{document_id}:{version_id}:parent:{index:03d}",
        document_id=document_id,
        version_id=version_id,
        source=source,
        title=title,
        text=text,
        page_start=_page_for_offset(start, boundaries),
        page_end=_page_for_offset(max(start, end - 1), boundaries),
    )
