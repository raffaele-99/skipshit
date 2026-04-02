"""OpenRouter LLM analyser implementation (OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from skipshit.analyser.base import ChunkConfig, TopicAnalyser
from skipshit.analyser.chunker import chunk_transcript
from skipshit.analyser.merger import merge_skip_segments
from skipshit.analyser.prompt import OPENAI_TOOL, SYSTEM_PROMPT
from skipshit.models import AnalysisResult, SkipSegment, Transcript, TranscriptChunk, _format_timestamp

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _chunk_label(chunk: TranscriptChunk) -> str:
    start = _format_timestamp(chunk.start_seconds)
    end = _format_timestamp(chunk.end_seconds)
    return f"chunk {chunk.chunk_index + 1} of {chunk.total_chunks} ({start}–{end})"


class OpenRouterAnalyser(TopicAnalyser):
    """Analyses transcripts using any model via OpenRouter."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-sonnet-4",
        max_retries: int = 3,
    ) -> None:
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            max_retries=max_retries,
        )
        self.model = model
        self._start_time = 0.0
        self._split_retries = False

    def _elapsed(self) -> float:
        return time.monotonic() - self._start_time

    def analyse(
        self,
        transcript: Transcript,
        topics: list[str],
        chunk_config: ChunkConfig | None = None,
    ) -> AnalysisResult:
        config = chunk_config or ChunkConfig()
        self._start_time = time.monotonic()
        self._split_retries = config.split_retries

        chunks = chunk_transcript(
            transcript,
            max_tokens=config.max_tokens,
            overlap_seconds=config.overlap_seconds,
        )
        logger.info("Split transcript into %d chunk(s)", len(chunks))

        all_segments: list[SkipSegment] = []
        total_cost = 0.0
        with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
            futures = {}
            for chunk in chunks:
                label = _chunk_label(chunk)
                logger.info("[%.1fs] Submitting %s", self._elapsed(), label)
                futures[pool.submit(self._analyse_chunk, chunk, topics, config.buffer_seconds)] = chunk
            logger.info("[%.1fs] All %d chunks submitted.", self._elapsed(), len(chunks))
            logger.info("[%.1fs] Waiting for responses from %s...", self._elapsed(), self.model)

            for future in as_completed(futures):
                chunk = futures[future]
                segments, cost = future.result()
                total_cost += cost
                all_segments.extend(segments)

        merged = merge_skip_segments(all_segments)
        elapsed = self._elapsed()
        logger.info("Total cost: $%.4f", total_cost)

        return AnalysisResult(
            video_url=f"https://www.youtube.com/watch?v={transcript.video_id}",
            video_title=transcript.video_title,
            duration_seconds=transcript.duration_seconds,
            skip_segments=merged,
            metadata={
                "transcript_source": transcript.source,
                "model_used": self.model,
                "processing_time_seconds": round(elapsed, 1),
                "chunks_analysed": len(chunks),
                "cost_usd": round(total_cost, 6),
            },
        )

    def _analyse_chunk(
        self,
        chunk: TranscriptChunk,
        topics: list[str],
        buffer_seconds: float,
        _retry: int = 0,
    ) -> tuple[list[SkipSegment], float]:
        label = _chunk_label(chunk)
        topics_str = ", ".join(f'"{t}"' for t in topics)
        user_message = (
            f"Here is {chunk.context_label}.\n\n"
            f"Topics to scan for: {topics_str}\n\n"
            f"Transcript:\n{chunk.text}"
        )

        chunk_start = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(buffer_seconds=int(buffer_seconds))},
                {"role": "user", "content": user_message},
            ],
            tools=[OPENAI_TOOL],
            tool_choice={"type": "function", "function": {"name": "report_skip_segments"}},
        )
        chunk_elapsed = time.monotonic() - chunk_start
        cost = getattr(response.usage, "cost", 0) or 0 if response.usage else 0

        if not response.choices:
            return self._handle_retry(chunk, label, topics, buffer_seconds, _retry, cost, chunk_elapsed)

        message = response.choices[0].message
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "report_skip_segments":
                    try:
                        tool_input = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(
                            "[%.1fs] Completed %s in %.1fs, but got malformed JSON. Retrying...",
                            self._elapsed(), label, chunk_elapsed,
                        )
                        return self._handle_retry(chunk, label, topics, buffer_seconds, _retry, cost, chunk_elapsed)
                    logger.info("[%.1fs] Completed %s in %.1fs", self._elapsed(), label, chunk_elapsed)
                    return _parse_tool_response(tool_input), cost

        # Model responded with text instead of a tool call
        text = getattr(message, "content", None) or ""
        if text:
            logger.info(
                "[%.1fs] Completed %s in %.1fs (text response, no segments)",
                self._elapsed(), label, chunk_elapsed,
            )
            return [], cost

        return self._handle_retry(chunk, label, topics, buffer_seconds, _retry, cost, chunk_elapsed)

    def _handle_retry(
        self,
        chunk: TranscriptChunk,
        label: str,
        topics: list[str],
        buffer_seconds: float,
        _retry: int,
        cost: float,
        chunk_elapsed: float,
    ) -> tuple[list[SkipSegment], float]:
        if _retry >= 2:
            logger.warning(
                "[%.1fs] Completed %s in %.1fs, but the response was empty. Skipping chunk.",
                self._elapsed(), label, chunk_elapsed,
            )
            return [], cost

        if self._split_retries and len(chunk.segments) > 1:
            logger.warning(
                "[%.1fs] Completed %s in %.1fs, but the response was empty. Splitting and retrying...",
                self._elapsed(), label, chunk_elapsed,
            )
            return self._split_and_retry(chunk, topics, buffer_seconds, cost)

        logger.warning(
            "[%.1fs] Completed %s in %.1fs, but the response was empty. Retrying (%d/2)...",
            self._elapsed(), label, chunk_elapsed, _retry + 1,
        )
        segments, retry_cost = self._analyse_chunk(chunk, topics, buffer_seconds, _retry + 1)
        return segments, cost + retry_cost

    def _split_and_retry(
        self,
        chunk: TranscriptChunk,
        topics: list[str],
        buffer_seconds: float,
        cost: float,
    ) -> tuple[list[SkipSegment], float]:
        mid = len(chunk.segments) // 2
        first_segs = chunk.segments[:mid]
        second_segs = chunk.segments[mid:]

        first_half = TranscriptChunk(
            segments=first_segs,
            start_seconds=first_segs[0].start_seconds,
            end_seconds=first_segs[-1].start_seconds + first_segs[-1].duration_seconds,
            chunk_index=chunk.chunk_index,
            total_chunks=chunk.total_chunks,
        )
        second_half = TranscriptChunk(
            segments=second_segs,
            start_seconds=second_segs[0].start_seconds,
            end_seconds=second_segs[-1].start_seconds + second_segs[-1].duration_seconds,
            chunk_index=chunk.chunk_index,
            total_chunks=chunk.total_chunks,
        )

        seg_a, cost_a = self._analyse_chunk(first_half, topics, buffer_seconds)
        seg_b, cost_b = self._analyse_chunk(second_half, topics, buffer_seconds)
        return seg_a + seg_b, cost + cost_a + cost_b


def _parse_tool_response(tool_input: dict) -> list[SkipSegment]:
    """Parse the structured tool response into SkipSegment objects."""
    segments = []
    for item in tool_input.get("segments", []):
        try:
            segments.append(
                SkipSegment(
                    start_seconds=float(item["start_seconds"]),
                    end_seconds=float(item["end_seconds"]),
                    reason=item["reason"],
                    matched_topics=item["matched_topics"],
                    confidence=item["confidence"],
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed segment from LLM response: %s (%s)", item, exc)
    return segments
