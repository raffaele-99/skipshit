"""Tests for the skip segment merger module."""

from __future__ import annotations

from skipshit.analyser.merger import merge_skip_segments
from skipshit.models import SkipSegment


def _seg(start: float, end: float, reason: str = "test", topics: list[str] | None = None, confidence: str = "high") -> SkipSegment:
    return SkipSegment(
        start_seconds=start,
        end_seconds=end,
        reason=reason,
        matched_topics=topics or ["topic"],
        confidence=confidence,
    )


class TestMergeSkipSegments:
    def test_empty(self):
        assert merge_skip_segments([]) == []

    def test_single_segment(self):
        seg = _seg(10, 20)
        result = merge_skip_segments([seg])
        assert len(result) == 1
        assert result[0].start_seconds == 10
        assert result[0].end_seconds == 20

    def test_non_overlapping_segments(self):
        result = merge_skip_segments([_seg(10, 20), _seg(200, 300)])
        assert len(result) == 2

    def test_overlapping_segments_merged(self):
        result = merge_skip_segments([_seg(10, 50), _seg(40, 80)])
        assert len(result) == 1
        assert result[0].start_seconds == 10
        assert result[0].end_seconds == 80

    def test_adjacent_within_gap_merged(self):
        result = merge_skip_segments([_seg(10, 50), _seg(100, 150)], merge_gap=60)
        assert len(result) == 1
        assert result[0].start_seconds == 10
        assert result[0].end_seconds == 150

    def test_adjacent_beyond_gap_not_merged(self):
        result = merge_skip_segments([_seg(10, 50), _seg(200, 250)], merge_gap=60)
        assert len(result) == 2

    def test_topics_unioned(self):
        a = _seg(10, 50, topics=["crypto"])
        b = _seg(40, 80, topics=["investing"])
        result = merge_skip_segments([a, b])
        assert result[0].matched_topics == ["crypto", "investing"]

    def test_duplicate_topics_deduplicated(self):
        a = _seg(10, 50, topics=["crypto", "bitcoin"])
        b = _seg(40, 80, topics=["crypto", "investing"])
        result = merge_skip_segments([a, b])
        assert result[0].matched_topics == ["crypto", "bitcoin", "investing"]

    def test_highest_confidence_kept(self):
        a = _seg(10, 50, confidence="low")
        b = _seg(40, 80, confidence="high")
        result = merge_skip_segments([a, b])
        assert result[0].confidence == "high"

    def test_longer_reason_kept(self):
        a = _seg(10, 50, reason="short")
        b = _seg(40, 80, reason="this is a much longer reason")
        result = merge_skip_segments([a, b])
        assert result[0].reason == "this is a much longer reason"

    def test_unsorted_input(self):
        result = merge_skip_segments([_seg(200, 300), _seg(10, 50), _seg(40, 80)])
        assert len(result) == 2
        assert result[0].start_seconds == 10
        assert result[1].start_seconds == 200

    def test_three_overlapping_merged(self):
        result = merge_skip_segments([_seg(10, 40), _seg(30, 70), _seg(60, 100)])
        assert len(result) == 1
        assert result[0].start_seconds == 10
        assert result[0].end_seconds == 100
