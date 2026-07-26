import pytest

from labs.rag.structured_pdf_ingestion import PdfSectionMarker, section_documents_from_text


def test_section_documents_preserve_configured_heading_as_metadata() -> None:
    markers = [
        PdfSectionMarker("first", "Birinci Başlık", "01 Birinci Başlık"),
        PdfSectionMarker("second", "İkinci Başlık", "02 İkinci Başlık"),
    ]

    documents = section_documents_from_text(
        "Giriş. 01 Birinci Başlık Birinci içerik. 02 İkinci Başlık İkinci içerik.",
        markers=markers,
        source="program.pdf",
    )

    assert [document.doc_id for document in documents] == ["first", "second"]
    assert documents[0].title == "Birinci Başlık"
    assert documents[0].text == "01 Birinci Başlık Birinci içerik."
    assert documents[1].text == "02 İkinci Başlık İkinci içerik."


def test_section_documents_reject_missing_marker() -> None:
    marker = PdfSectionMarker("first", "Birinci Başlık", "01 Birinci Başlık")

    with pytest.raises(ValueError, match="section marker not found"):
        section_documents_from_text("Başlıksız metin.", markers=[marker], source="program.pdf")
