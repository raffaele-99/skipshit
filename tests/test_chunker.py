"""Tests for the transcript chunker module."""

from __future__ import annotations

from skipshit.analyser.chunker import chunk_transcript, estimate_tokens
from skipshit.models import Transcript, TranscriptSegment


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens([]) == 0

    def test_known_text(self):
        segs = [TranscriptSegment(text="hello world", start_seconds=0, duration_seconds=1)]
        tokens = estimate_tokens(segs)
        # "hello world" = 11 chars + 20 overhead = 31 chars / 4 = 7 tokens
        assert tokens == 7


class TestChunkTranscript:
    def test_short_transcript_single_chunk(self, sample_transcript: Transcript):
        chunks = chunk_transcript(sample_transcript, max_tokens=100_000)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1
        assert chunks[0].segments == sample_transcript.segments

    def test_long_transcript_multiple_chunks(self, long_transcript: Transcript):
        chunks = chunk_transcript(long_transcript, max_tokens=10_000)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)
            assert len(chunk.segments) > 0

    def test_chunks_cover_full_transcript(self, long_transcript: Transcript):
        chunks = chunk_transcript(long_transcript, max_tokens=10_000)
        all_starts = set()
        for chunk in chunks:
            for seg in chunk.segments:
                all_starts.add(seg.start_seconds)
        original_starts = {seg.start_seconds for seg in long_transcript.segments}
        assert original_starts == all_starts

    def test_chunks_have_overlap(self, long_transcript: Transcript):
        chunks = chunk_transcript(long_transcript, max_tokens=10_000, overlap_seconds=120.0)
        if len(chunks) < 2:
            return
        for i in range(1, len(chunks)):
            prev_end = chunks[i - 1].end_seconds
            curr_start = chunks[i].start_seconds
            assert curr_start < prev_end, "Chunks should overlap"

    def test_empty_transcript(self):
        t = Transcript(video_id="x", segments=[], source="test")
        chunks = chunk_transcript(t)
        assert chunks == []

    def test_context_label(self, sample_transcript: Transcript):
        chunks = chunk_transcript(sample_transcript, max_tokens=100_000)
        label = chunks[0].context_label
        assert "chunk 1 of 1" in label
