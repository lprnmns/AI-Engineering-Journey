from pathlib import Path

import pytest

from labs.rag import pdf_ingestion


def test_pdf_to_document_raises_when_no_text_is_extracted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_ingestion, "extract_pdf_text", lambda _: "")

    with pytest.raises(ValueError, match="no selectable text"):
        pdf_ingestion.pdf_to_document(Path("empty.pdf"))
