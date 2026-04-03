"""skipshit — YouTube topic-filtering tool."""

from __future__ import annotations

__version__ = "0.1.0"

from skipshit.analyser.base import ChunkConfig
from skipshit.models import AnalysisResult


def analyse(
    url: str,
    topics: list[str],
    *,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    buffer_seconds: float = 30.0,
    max_tokens: int = 8_000,
    overlap_seconds: float = 120.0,
    split_retries: bool = False,
    language: str = "en",
) -> AnalysisResult:
    """Analyse a YouTube video and return skip segments for the given topics.

    Args:
        url: YouTube video URL or video ID.
        topics: List of topics to scan for.
        api_key: API key. Falls back to OPENROUTER_API_KEY / ANTHROPIC_API_KEY env vars.
        model: Model to use (default: openai/gpt-5-nano).
        provider: "openrouter" or "anthropic" (auto-detected from model name).
        buffer_seconds: Seconds of buffer around flagged segments.
        max_tokens: Max tokens per chunk.
        overlap_seconds: Overlap between chunks in seconds.
        split_retries: Split failed chunks in half before retrying.
        language: Transcript language preference.

    Returns:
        AnalysisResult with skip_segments, metadata, etc.
    """
    from skipshit.config import load_config
    from skipshit.transcript import get_transcript

    cfg = load_config(
        cli_topics=topics,
        cli_model=model,
        cli_api_key=api_key,
        cli_provider=provider,
    )

    if not topics:
        raise ValueError("No topics specified.")
    if not cfg.api_key:
        raise ValueError(
            "No API key found. Pass api_key or set OPENROUTER_API_KEY / ANTHROPIC_API_KEY."
        )

    transcript = get_transcript(url, language=language)

    if cfg.provider == "openrouter":
        from skipshit.analyser.openrouter import OpenRouterAnalyser
        analyser = OpenRouterAnalyser(api_key=cfg.api_key, model=cfg.model)
    else:
        from skipshit.analyser.claude import ClaudeAnalyser
        analyser = ClaudeAnalyser(api_key=cfg.api_key, model=cfg.model)

    chunk_config = ChunkConfig(
        buffer_seconds=buffer_seconds,
        max_tokens=max_tokens,
        overlap_seconds=overlap_seconds,
        split_retries=split_retries,
    )

    return analyser.analyse(transcript, topics, chunk_config)
