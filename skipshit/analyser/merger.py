"""Merge and deduplicate skip segments from multiple analysis chunks."""

from __future__ import annotations

from skipshit.models import SkipSegment

MERGE_GAP_SECONDS = 60.0

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def merge_skip_segments(
    segments: list[SkipSegment],
    merge_gap: float = MERGE_GAP_SECONDS,
) -> list[SkipSegment]:
    """Merge overlapping or adjacent skip segments into consolidated ranges."""
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda s: s.start_seconds)
    merged: list[SkipSegment] = []

    current = sorted_segs[0]
    for next_seg in sorted_segs[1:]:
        if next_seg.start_seconds <= current.end_seconds + merge_gap:
            current = _merge_pair(current, next_seg)
        else:
            merged.append(current)
            current = next_seg

    merged.append(current)
    return merged


def _merge_pair(a: SkipSegment, b: SkipSegment) -> SkipSegment:
    """Merge two overlapping/adjacent skip segments."""
    topics = list(dict.fromkeys(a.matched_topics + b.matched_topics))

    # Keep the longer reason as the more descriptive one
    reason = a.reason if len(a.reason) >= len(b.reason) else b.reason

    conf_a = _CONFIDENCE_RANK.get(a.confidence, 0)
    conf_b = _CONFIDENCE_RANK.get(b.confidence, 0)
    confidence = a.confidence if conf_a >= conf_b else b.confidence

    return SkipSegment(
        start_seconds=min(a.start_seconds, b.start_seconds),
        end_seconds=max(a.end_seconds, b.end_seconds),
        reason=reason,
        matched_topics=topics,
        confidence=confidence,
    )
