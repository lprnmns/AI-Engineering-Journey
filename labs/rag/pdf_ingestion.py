from __future__ import annotations

from pathlib import Path

from labs.rag.sample_docs import Document


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract and normalize selectable text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)
    return " ".join(text.split())


def pdf_to_document(pdf_path: Path, doc_id: str | None = None) -> Document:
    text = extract_pdf_text(pdf_path)
    if not text:
        raise ValueError(f"no selectable text extracted from PDF: {pdf_path}")

    return Document(
        doc_id=doc_id or pdf_path.stem.lower().replace(" ", "_"),
        title=pdf_path.stem,
        text=text,
        source=pdf_path.name,
    )
