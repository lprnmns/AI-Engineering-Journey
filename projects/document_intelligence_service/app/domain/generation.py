"""Framework-independent answer generation boundary objects."""

from dataclasses import dataclass


class AnswerGenerationError(RuntimeError):
    """Raised when the configured local generation dependency cannot answer."""


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """One answer returned by an external/local generator adapter."""

    answer: str
    provider: str
    model: str
    latency_ms: float
