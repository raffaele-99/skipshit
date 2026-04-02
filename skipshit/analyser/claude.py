"""Claude/Anthropic LLM analyser implementation."""

from __future__ import annotations

import logging
import time

import anthropic

from skipshit.analyser.base import ChunkConfig, TopicAnalyser
from skipshit.analyser.chunker import chunk_transcript
from skipshit.analyser.merger import merge_skip_segments
from skipshit.analyser.prompt import ANTHROPIC_TOOL, SYSTEM_PROMPT
from skipshit.models import AnalysisResult, SkipSegment, Transcript, TranscriptChunk

logger = logging.getLogger(__name__)


class ClaudeAnalyser(TopicAnalyser):
    """Analyses transcripts using Claude via the Anthropic API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3,
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)
        self.model = model

    def analyse(
        self,
        transcript: Transcript,
        topics: list[str],
        chunk_config: ChunkConfig | None = None,
    ) -> AnalysisResult:
        config = chunk_config or ChunkConfig()
        start_time = time.monotonic()

        chunks = chunk_transcript(
            transcript,
            max_tokens=config.max_tokens,
            overlap_seconds=config.overlap_seconds,
        )
        logger.info("Split transcript into %d chunk(s)", len(chunks))

        all_segments: list[SkipSegment] = []
        for chunk in chunks:
            logger.info("Analysing %s", chunk.context_label)
            segments = self._analyse_chunk(chunk, topics, config.buffer_seconds)
            all_segments.extend(segments)

        merged = merge_skip_segments(all_segments)
        elapsed = time.monotonic() - start_time

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
            },
        )

    def _analyse_chunk(
        self,
        chunk: TranscriptChunk,
        topics: list[str],
        buffer_seconds: float,
    ) -> list[SkipSegment]:
        topics_str = ", ".join(f'"{t}"' for t in topics)
        user_message = (
            f"Here is {chunk.context_label}.\n\n"
            f"Topics to scan for: {topics_str}\n\n"
            f"Transcript:\n{chunk.text}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT.format(buffer_seconds=int(buffer_seconds)),
            messages=[{"role": "user", "content": user_message}],
            tools=[ANTHROPIC_TOOL],
            tool_choice={"type": "tool", "name": "report_skip_segments"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "report_skip_segments":
                return _parse_tool_response(block.input)

        logger.warning("No tool_use block in Claude response for %s", chunk.context_label)
        return []


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
