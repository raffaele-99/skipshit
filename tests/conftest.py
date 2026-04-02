"""Shared fixtures for skipshit tests."""

from __future__ import annotations

import pytest

from skipshit.models import Transcript, TranscriptSegment


@pytest.fixture
def sample_segments() -> list[TranscriptSegment]:
    """A short list of transcript segments for testing."""
    return [
        TranscriptSegment(text="Welcome to the podcast everyone.", start_seconds=0.0, duration_seconds=3.0),
        TranscriptSegment(text="Today we're going to talk about cooking.", start_seconds=3.0, duration_seconds=4.0),
        TranscriptSegment(text="First up, let's discuss pasta recipes.", start_seconds=7.0, duration_seconds=3.5),
        TranscriptSegment(text="Now let's talk about crypto investments.", start_seconds=60.0, duration_seconds=5.0),
        TranscriptSegment(text="Bitcoin has been going crazy lately.", start_seconds=65.0, duration_seconds=4.0),
        TranscriptSegment(text="You should definitely buy some altcoins.", start_seconds=69.0, duration_seconds=4.0),
        TranscriptSegment(text="Anyway, back to cooking.", start_seconds=120.0, duration_seconds=3.0),
        TranscriptSegment(text="Let me show you this amazing recipe.", start_seconds=123.0, duration_seconds=4.0),
        TranscriptSegment(text="And that's all for today, thanks for watching!", start_seconds=180.0, duration_seconds=5.0),
    ]


@pytest.fixture
def sample_transcript(sample_segments: list[TranscriptSegment]) -> Transcript:
    """A sample transcript for testing."""
    return Transcript(
        video_id="test123",
        video_title="Test Podcast Episode",
        duration_seconds=185.0,
        segments=sample_segments,
        source="youtube_captions",
    )


@pytest.fixture
def long_transcript() -> Transcript:
    """A long transcript that will need chunking."""
    segments = []
    for i in range(5000):
        segments.append(
            TranscriptSegment(
                text=f"This is segment number {i} with some filler text to make it longer for token estimation purposes.",
                start_seconds=float(i * 5),
                duration_seconds=5.0,
            )
        )
    return Transcript(
        video_id="long123",
        video_title="Very Long Podcast",
        duration_seconds=25000.0,
        segments=segments,
        source="youtube_captions",
    )
