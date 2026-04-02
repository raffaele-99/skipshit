"""Configuration loading from CLI args, env vars, and config files."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    """Resolved configuration for a skipshit run."""

    api_key: str | None = None
    provider: str = "anthropic"  # "anthropic" or "openrouter"
    model: str = "claude-sonnet-4-20250514"
    avoid_topics: list[str] = field(default_factory=list)
    buffer_seconds: float = 30.0
    max_tokens: int = 8_000
    overlap_seconds: float = 120.0
    language: str = "en"


# Models that contain a slash are OpenRouter-style (e.g. "openai/gpt-5-nano")
def _infer_provider(model: str, explicit_provider: str | None) -> str:
    if explicit_provider:
        return explicit_provider
    if "/" in model:
        return "openrouter"
    return "anthropic"


def load_config(
    config_path: str | None = None,
    cli_topics: tuple[str, ...] | list[str] = (),
    cli_model: str | None = None,
    cli_buffer: float | None = None,
    cli_api_key: str | None = None,
    cli_provider: str | None = None,
) -> Config:
    """Build a Config by layering: config file < env vars < CLI args."""
    file_config = _load_config_file(config_path)

    model = (
        cli_model
        or os.environ.get("SKIPSHIT_MODEL")
        or file_config.get("model", "openai/gpt-5-nano")
    )

    provider = _infer_provider(
        model,
        cli_provider
        or os.environ.get("SKIPSHIT_PROVIDER")
        or file_config.get("provider"),
    )

    if provider == "openrouter":
        api_key = (
            cli_api_key
            or os.environ.get("SKIPSHIT_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or file_config.get("api_key")
        )
    else:
        api_key = (
            cli_api_key
            or os.environ.get("SKIPSHIT_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or file_config.get("api_key")
        )

    buffer = cli_buffer if cli_buffer is not None else file_config.get("buffer_seconds", 30.0)

    file_topics = file_config.get("avoid_topics", [])
    topics = list(cli_topics) if cli_topics else file_topics

    return Config(
        api_key=api_key,
        provider=provider,
        model=model,
        avoid_topics=topics,
        buffer_seconds=buffer,
        language=file_config.get("language", "en"),
    )


def _config_dir() -> Path:
    """Return the XDG-compliant config directory."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "skipshit"
    return Path.home() / ".config" / "skipshit"


def _load_config_file(path: str | None) -> dict:
    """Load a YAML config file, returning an empty dict on failure.

    Search order:
      1. Explicit --config path
      2. $XDG_CONFIG_HOME/skipshit/config.yaml (or .yml)
      3. ~/.skipshit.yaml (or .yml) — legacy fallback
    """
    candidates = []
    if path:
        candidates.append(Path(path))

    cfg_dir = _config_dir()
    candidates.append(cfg_dir / "config.yaml")
    candidates.append(cfg_dir / "config.yml")

    # Legacy locations
    candidates.append(Path.home() / ".skipshit.yaml")
    candidates.append(Path.home() / ".skipshit.yml")

    for p in candidates:
        if p.is_file():
            with open(p) as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    return {}
