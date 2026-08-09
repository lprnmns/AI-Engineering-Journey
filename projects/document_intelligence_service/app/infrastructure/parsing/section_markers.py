"""Named section-marker profiles for known document families."""

from typing import Literal

from ...domain.chunks import SectionMarker

SectionMarkerProfile = Literal["none", "mentor_program_v1"]


MENTOR_PROGRAM_V1_MARKERS: tuple[SectionMarker, ...] = (
    SectionMarker("purpose", "Programın Amacı"),
    SectionMarker("model_fundamentals", "01 Modelin nasıl düşündüğünü anla"),
    SectionMarker("embedding", "02 Embedding ve anlamsal aramayı somutlaştır"),
    SectionMarker("rag", "03 RAG akışının tamamını kur"),
    SectionMarker("local_model", "04 Yerel modeli ayağa kaldır ve karşılaştır"),
    SectionMarker("corporate_problem", "05 Gerçek bir kurumsal problem seç"),
    SectionMarker("deliverables", "Teslim Paketi"),
)


def get_section_markers(
    profile: SectionMarkerProfile | str,
) -> tuple[SectionMarker, ...]:
    """Return immutable markers for one explicit profile."""

    if profile == "none":
        return ()
    if profile == "mentor_program_v1":
        return MENTOR_PROGRAM_V1_MARKERS
    raise ValueError(f"Unknown section marker profile: {profile}")
