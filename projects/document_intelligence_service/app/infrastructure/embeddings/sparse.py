"""Deterministic lexical sparse encoder for the first hybrid spike."""

from collections import Counter
from collections.abc import Sequence
import hashlib
import math
import re

from ...domain.vectors import SparseVector

_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


class HashingSparseEncoder:
    """Map normalized term frequencies to stable sparse feature IDs.

    Qdrant's IDF modifier supplies collection-level inverse document frequency
    during search. This adapter deliberately owns only deterministic tokenization
    and term-frequency encoding; a later spike will compare it with a fitted
    corpus-aware BM25 adapter.
    """

    def __init__(self, *, feature_count: int = 1_048_576) -> None:
        if feature_count <= 0:
            raise ValueError("feature_count must be greater than zero")
        self._feature_count = feature_count

    def embed_documents(self, texts: Sequence[str]) -> tuple[SparseVector, ...]:
        """Encode each text into sorted, unique sparse index/value pairs."""

        return tuple(self._encode_one(text) for text in texts)

    def _encode_one(self, text: str) -> SparseVector:
        counts = Counter(token.casefold() for token in _TOKEN_PATTERN.findall(text))
        pairs = sorted(
            (
                self._feature_index(token),
                1.0 + math.log(float(term_count)),
            )
            for token, term_count in counts.items()
        )
        # Hash collisions can produce the same feature index; merge them before
        # constructing the value object, which requires unique sorted indices.
        merged: dict[int, float] = {}
        for index, value in pairs:
            merged[index] = merged.get(index, 0.0) + value
        return SparseVector(
            indices=tuple(sorted(merged)),
            values=tuple(merged[index] for index in sorted(merged)),
        )

    def _feature_index(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big") % self._feature_count
