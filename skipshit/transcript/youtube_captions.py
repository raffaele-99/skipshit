"""Transcript fetcher using youtube-transcript-api."""

from __future__ import annotations

import logging

from youtube_transcript_api import YouTubeTranscriptApi

from skipshit.models import Transcript, TranscriptSegment
from skipshit.transcript.base import TranscriptFetcher

logger = logging.getLogger(__name__)


class YouTubeCaptionsFetcher(TranscriptFetcher):
    """Fetches transcripts via the youtube-transcript-api library."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def fetch(self, video_id: str) -> Transcript:
        logger.info("Fetching transcript for %s via youtube-transcript-api", video_id)

        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id, languages=[self.language])

        segments = [
            TranscriptSegment(
                text=entry.text,
                start_seconds=entry.start,
                duration_seconds=entry.duration,
            )
            for entry in transcript_data
        ]

        if not segments:
            raise RuntimeError(
                f"No transcript segments found for video {video_id}"
            )

        duration = segments[-1].start_seconds + segments[-1].duration_seconds

        return Transcript(
            video_id=video_id,
            video_title=None,
            duration_seconds=duration,
            segments=segments,
            source="youtube_captions",
        )
