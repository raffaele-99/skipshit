"""Abstract base class for LLM-based topic analysers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from skipshit.models import AnalysisResult, Transcript


@dataclass
class ChunkConfig:
    """Configuration for transcript chunking."""

    max_tokens: int = 8_000
    overlap_seconds: float = 120.0
    buffer_seconds: float = 30.0
    split_retries: bool = False


class TopicAnalyser(ABC):
    """Interface for LLM-based topic analysis of transcripts."""

    @abstractmethod
    def analyse(
        self,
        transcript: Transcript,
        topics: list[str],
        chunk_config: ChunkConfig | None = None,
    ) -> AnalysisResult:
        """Analyse a transcript and return skip segments for the given topics."""
