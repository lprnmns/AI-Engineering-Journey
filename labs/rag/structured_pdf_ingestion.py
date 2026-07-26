from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labs.rag.sample_docs import Document


@dataclass(frozen=True)
class PdfSectionMarker:
    """A known section heading used to preserve document structure during ingestion."""

    doc_id: str
    title: str
    marker: str


def normalize_pdf_page_text(text: str, repeated_prefix: str = "") -> str:
    normalized = " ".join(text.split())
    if repeated_prefix:
        normalized = normalized.removeprefix(repeated_prefix).strip()
    return normalized


def extract_pdf_pages(
    pdf_path: Path,
    repeated_prefix: str = "",
) -> list[str]:
    """Extract normalized text one page at a time while retaining page boundaries."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [
        normalize_pdf_page_text(page.extract_text() or "", repeated_prefix)
        for page in reader.pages
    ]
    return [page for page in pages if page]


def section_documents_from_text(
    text: str,
    markers: list[PdfSectionMarker],
    source: str,
) -> list[Document]:
    """Split text into ordered, explicitly configured sections.

    This deliberately uses supplied headings instead of guessing every PDF layout.
    A production parser should select such rules per document family and evaluate them.
    """
    if not markers:
        raise ValueError("markers must not be empty")

    positions: list[tuple[int, PdfSectionMarker]] = []
    for marker in markers:
        position = text.find(marker.marker)
        if position < 0:
            raise ValueError(f"section marker not found: {marker.marker}")
        positions.append((position, marker))

    if positions != sorted(positions, key=lambda item: item[0]):
        raise ValueError("section markers must appear in document order")

    documents: list[Document] = []
    for index, (start, marker) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        section_text = text[start:end].strip()
        documents.append(
            Document(
                doc_id=marker.doc_id,
                title=marker.title,
                text=section_text,
                source=source,
            )
        )
    return documents


def pdf_to_section_documents(
    pdf_path: Path,
    markers: list[PdfSectionMarker],
    repeated_prefix: str = "",
) -> list[Document]:
    pages = extract_pdf_pages(pdf_path, repeated_prefix=repeated_prefix)
    if not pages:
        raise ValueError(f"no selectable text extracted from PDF: {pdf_path}")

    return section_documents_from_text(
        text=" ".join(pages),
        markers=markers,
        source=pdf_path.name,
    )
