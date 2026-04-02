"""Tests for the transcript fetching module."""

from __future__ import annotations

import pytest

from skipshit.transcript.base import TranscriptFetcher


class TestExtractVideoId:
    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert TranscriptFetcher.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert TranscriptFetcher.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert TranscriptFetcher.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLtest"
        assert TranscriptFetcher.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_bare_video_id(self):
        assert TranscriptFetcher.extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_whitespace(self):
        url = "  https://youtu.be/dQw4w9WgXcQ  "
        assert TranscriptFetcher.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not extract video ID"):
            TranscriptFetcher.extract_video_id("https://example.com/not-youtube")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            TranscriptFetcher.extract_video_id("")
