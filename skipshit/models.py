"""Data structures shared across all skipshit modules."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single captioned line from a video transcript."""

    text: str
    start_seconds: float
    duration_seconds: float


class Transcript(BaseModel):
    """A full video transcript composed of captioned segments."""

    video_id: str
    video_title: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptSegment]
    source: str = Field(description="e.g. 'youtube_captions', 'yt_dlp'")

    @property
    def full_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    @property
    def end_seconds(self) -> float:
        if not self.segments:
            return 0.0
        last = self.segments[-1]
        return last.start_seconds + last.duration_seconds


class TranscriptChunk(BaseModel):
    """A subset of transcript segments with positional context."""

    segments: list[TranscriptSegment]
    start_seconds: float
    end_seconds: float
    chunk_index: int
    total_chunks: int

    @property
    def context_label(self) -> str:
        return (
            f"chunk {self.chunk_index + 1} of {self.total_chunks}, "
            f"covering {_format_timestamp(self.start_seconds)}–{_format_timestamp(self.end_seconds)}"
        )

    @property
    def text(self) -> str:
        return "\n".join(
            f"[{_format_timestamp(s.start_seconds)}] {s.text}" for s in self.segments
        )


class SkipSegment(BaseModel):
    """A flagged time range that the user may want to skip."""

    start_seconds: float
    end_seconds: float
    reason: str
    matched_topics: list[str]
    confidence: Literal["high", "medium", "low"]

    @property
    def start_timestamp(self) -> str:
        return _format_timestamp(self.start_seconds)

    @property
    def end_timestamp(self) -> str:
        return _format_timestamp(self.end_seconds)

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


class AnalysisResult(BaseModel):
    """The final output of the skip-analysis pipeline."""

    video_url: str
    video_title: str | None = None
    duration_seconds: float | None = None
    skip_segments: list[SkipSegment] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @property
    def total_skip_seconds(self) -> float:
        return sum(seg.duration_seconds for seg in self.skip_segments)

    def to_json(self, indent: int = 2) -> str:
        data = {
            "video_url": self.video_url,
            "video_title": self.video_title,
            "duration_seconds": self.duration_seconds,
            "skip_segments": [
                {
                    "start": seg.start_timestamp,
                    "end": seg.end_timestamp,
                    "start_seconds": seg.start_seconds,
                    "end_seconds": seg.end_seconds,
                    "reason": seg.reason,
                    "matched_topics": seg.matched_topics,
                    "confidence": seg.confidence,
                }
                for seg in self.skip_segments
            ],
            "metadata": self.metadata,
        }
        return json.dumps(data, indent=indent)

    def to_text(self) -> str:
        title = self.video_title or "Unknown Video"
        lines = [f'Skip Segments for "{title}":', ""]

        if not self.skip_segments:
            lines.append("  No segments matched the specified topics.")
            return "\n".join(lines)

        for i, seg in enumerate(self.skip_segments, 1):
            lines.append(
                f"  {i}. [{seg.start_timestamp} → {seg.end_timestamp}] {seg.reason}"
            )
            topics_str = " | ".join(seg.matched_topics)
            lines.append(
                f"     Topics: {topics_str} | Confidence: {seg.confidence}"
            )
            lines.append("")

        total_skip = self.total_skip_seconds
        duration = self.duration_seconds
        lines.append(
            f"Total skip time: {_format_duration(total_skip)}"
            + (f" (of {_format_duration(duration)})" if duration else "")
        )

        cost = self.metadata.get("cost_usd")
        if cost is not None:
            lines.append(f"Cost: ${cost:.4f}")

        return "\n".join(lines)

    def merge(self, other: AnalysisResult) -> AnalysisResult:
        """Combine two results, merging overlapping skip segments."""
        from skipshit.analyser.merger import merge_skip_segments

        all_segments = self.skip_segments + other.skip_segments
        merged = merge_skip_segments(all_segments)
        return AnalysisResult(
            video_url=self.video_url,
            video_title=self.video_title or other.video_title,
            duration_seconds=self.duration_seconds or other.duration_seconds,
            skip_segments=merged,
            metadata={**self.metadata, **other.metadata},
        )


def _format_timestamp(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_duration(seconds: float | None) -> str:
    """Format seconds as a human-readable duration string."""
    if seconds is None:
        return "unknown"
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h > 0:
        parts.append(f"{h} hr")
    if m > 0:
        parts.append(f"{m} min")
    if s > 0 or not parts:
        parts.append(f"{s} sec")
    return " ".join(parts)
