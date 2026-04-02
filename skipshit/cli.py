"""CLI entry point for skipshit."""

from __future__ import annotations

import logging
import sys

import click

from skipshit.analyser.base import ChunkConfig, TopicAnalyser
from skipshit.config import load_config
from skipshit.transcript import get_transcript


def _build_analyser(provider: str, api_key: str, model: str) -> TopicAnalyser:
    if provider == "openrouter":
        from skipshit.analyser.openrouter import OpenRouterAnalyser
        return OpenRouterAnalyser(api_key=api_key, model=model)
    else:
        from skipshit.analyser.claude import ClaudeAnalyser
        return ClaudeAnalyser(api_key=api_key, model=model)


@click.command()
@click.argument("youtube_url")
@click.option(
    "--avoid", "-a",
    multiple=True,
    help="Topic to skip (repeatable).",
)
@click.option(
    "--config", "-c", "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to YAML/JSON config file with saved topics.",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output file path (default: stdout).",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Output format (default: json).",
)
@click.option(
    "--buffer",
    type=float,
    default=None,
    help="Buffer seconds around flagged segments (default: 30).",
)
@click.option(
    "--model",
    default=None,
    help="LLM model to use (default: anthropic/claude-sonnet-4). Use provider/model format for OpenRouter.",
)
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openrouter"]),
    default=None,
    help="LLM provider (auto-detected from model name if not set).",
)
@click.option(
    "--split-retries",
    is_flag=True,
    help="Split failed chunks in half before retrying.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show progress and debug info.",
)
def main(
    youtube_url: str,
    avoid: tuple[str, ...],
    config_path: str | None,
    output: str | None,
    output_format: str,
    buffer: float | None,
    model: str | None,
    provider: str | None,
    split_retries: bool,
    verbose: bool,
) -> None:
    """Analyse a YouTube video and identify segments to skip based on topics."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s" if not verbose else "%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    # Suppress noisy HTTP debug logs unless -v is passed
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    cfg = load_config(
        config_path=config_path,
        cli_topics=avoid,
        cli_model=model,
        cli_buffer=buffer,
        cli_provider=provider,
    )

    if not cfg.avoid_topics:
        raise click.UsageError(
            "No topics specified. Use --avoid or provide a config file with avoid_topics."
        )

    if not cfg.api_key:
        env_hint = "OPENROUTER_API_KEY" if cfg.provider == "openrouter" else "ANTHROPIC_API_KEY"
        raise click.UsageError(
            f"No API key found. Set {env_hint} or SKIPSHIT_API_KEY, "
            "or add api_key to your config file."
        )

    transcript = get_transcript(youtube_url, language=cfg.language)
    click.echo(
        f"Fetched transcript: {len(transcript.segments)} segments, "
        f"source={transcript.source}",
        err=True,
    )

    analyser = _build_analyser(cfg.provider, cfg.api_key, cfg.model)
    chunk_config = ChunkConfig(
        buffer_seconds=cfg.buffer_seconds,
        max_tokens=cfg.max_tokens,
        overlap_seconds=cfg.overlap_seconds,
        split_retries=split_retries,
    )
    result = analyser.analyse(transcript, cfg.avoid_topics, chunk_config)

    if output_format == "json":
        text = result.to_json()
    else:
        text = result.to_text()

    if output:
        with open(output, "w") as f:
            f.write(text + "\n")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)


if __name__ == "__main__":
    main()
