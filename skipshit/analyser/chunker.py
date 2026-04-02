"""Split transcripts into overlapping chunks that fit within LLM context windows."""

from __future__ import annotations

from skipshit.models import Transcript, TranscriptChunk, TranscriptSegment

CHARS_PER_TOKEN = 4


def estimate_tokens(segments: list[TranscriptSegment]) -> int:
    """Estimate token count using a simple character-based heuristic."""
    total_chars = sum(len(s.text) + 20 for s in segments)  # +20 for timestamp prefix
    return total_chars // CHARS_PER_TOKEN


def chunk_transcript(
    transcript: Transcript,
    max_tokens: int = 80_000,
    overlap_seconds: float = 120.0,
) -> list[TranscriptChunk]:
    """Split a transcript into overlapping chunks.

    Each chunk fits within max_tokens and overlaps with the previous chunk
    by overlap_seconds to avoid missing topics that span chunk boundaries.
    """
    segments = transcript.segments
    if not segments:
        return []

    total_tokens = estimate_tokens(segments)
    if total_tokens <= max_tokens:
        return [
            TranscriptChunk(
                segments=segments,
                start_seconds=segments[0].start_seconds,
                end_seconds=segments[-1].start_seconds + segments[-1].duration_seconds,
                chunk_index=0,
                total_chunks=1,
            )
        ]

    chunks: list[TranscriptChunk] = []
    start_idx = 0

    while start_idx < len(segments):
        end_idx = start_idx
        while end_idx < len(segments) and estimate_tokens(segments[start_idx : end_idx + 1]) <= max_tokens:
            end_idx += 1
        # end_idx is now one past the last segment that fits
        if end_idx == start_idx:
            # Single segment exceeds max_tokens — include it anyway
            end_idx = start_idx + 1

        chunk_segments = segments[start_idx:end_idx]
        chunks.append(
            TranscriptChunk(
                segments=chunk_segments,
                start_seconds=chunk_segments[0].start_seconds,
                end_seconds=chunk_segments[-1].start_seconds + chunk_segments[-1].duration_seconds,
                chunk_index=len(chunks),
                total_chunks=0,  # filled in below
            )
        )

        if end_idx >= len(segments):
            break

        # Find the start of the next chunk: back up by overlap_seconds
        overlap_start_time = segments[end_idx].start_seconds - overlap_seconds
        next_start = end_idx
        while next_start > start_idx and segments[next_start].start_seconds > overlap_start_time:
            next_start -= 1
        # Ensure forward progress
        if next_start <= start_idx:
            next_start = end_idx
        start_idx = next_start

    for chunk in chunks:
        chunk.total_chunks = len(chunks)

    return chunks
