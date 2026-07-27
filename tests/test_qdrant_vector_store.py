from qdrant_client import QdrantClient

from labs.rag.chunking import Chunk
from labs.rag.qdrant_vector_store import QdrantVectorStore


class FakeVectorizer:
    def vectorize(self, text: str) -> list[float]:
        return [1.0, 0.0] if "yerel" in text.casefold() else [0.0, 1.0]


def make_chunk(chunk_id: str, section_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=section_id,
        title=section_id,
        text=text,
        source="mentor.pdf",
        chunk_index=1,
    )


def test_qdrant_store_upserts_stably_and_filters_by_section() -> None:
    store = QdrantVectorStore(
        collection_name="test_chunks",
        client=QdrantClient(":memory:"),
        vectorizer=FakeVectorizer(),
        vector_size=2,
    )
    local_chunk = make_chunk("local_chunk", "local_model", "Yerel model ölçümü.")
    delivery_chunk = make_chunk("delivery_chunk", "deliverables", "Teslim paketi.")

    store.upsert_chunks([local_chunk, delivery_chunk])
    store.upsert_chunks([local_chunk])

    assert store.stats().point_count == 2
    results = store.search("Yerel model", top_k=2, section_id="local_model")
    assert [result.chunk_id for result in results] == ["local_chunk"]
    assert results[0].doc_id == "local_model"


def test_qdrant_store_rejects_vector_dimension_mismatch() -> None:
    store = QdrantVectorStore(
        collection_name="test_dimensions",
        client=QdrantClient(":memory:"),
        vectorizer=FakeVectorizer(),
        vector_size=3,
    )

    try:
        store.upsert_chunks([make_chunk("local_chunk", "local_model", "Yerel model.")])
    except ValueError as error:
        assert "expected 3" in str(error)
    else:
        raise AssertionError("expected a vector dimension mismatch")
