"""Transcript fetching module."""

from __future__ import annotations

import logging

from skipshit.models import Transcript
from skipshit.transcript.youtube_captions import YouTubeCaptionsFetcher
from skipshit.transcript.yt_dlp import YtDlpFetcher

logger = logging.getLogger(__name__)


def get_transcript(url: str, language: str = "en") -> Transcript:
    """Fetch a transcript, trying youtube-transcript-api first, then yt-dlp."""
    video_id = YouTubeCaptionsFetcher.extract_video_id(url)

    primary = YouTubeCaptionsFetcher(language=language)
    try:
        return primary.fetch(video_id)
    except Exception as exc:
        logger.warning("Primary fetcher failed: %s. Trying yt-dlp fallback.", exc)

    fallback = YtDlpFetcher(language=language)
    return fallback.fetch(video_id)
