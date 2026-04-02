"""Abstract base class for transcript fetchers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from skipshit.models import Transcript

_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"^([a-zA-Z0-9_-]{11})$"),
]


class TranscriptFetcher(ABC):
    """Interface for fetching video transcripts."""

    @abstractmethod
    def fetch(self, video_id: str) -> Transcript:
        """Fetch the transcript for a given video ID."""

    @classmethod
    def extract_video_id(cls, url: str) -> str:
        """Extract the 11-character YouTube video ID from various URL formats."""
        url = url.strip()
        for pattern in _VIDEO_ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract video ID from: {url}")
