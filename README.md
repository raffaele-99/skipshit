# skipshit

A CLI tool that takes a YouTube video URL and a list of topics you want to avoid, then tells you exactly which segments to skip and why.

## Install

```bash
pip install -e .
```

## Usage

Set your API key — either OpenRouter or Anthropic:

```bash
# OpenRouter (supports Claude and many other models)
export OPENROUTER_API_KEY=sk-or-...

# Or Anthropic directly
export ANTHROPIC_API_KEY=sk-ant-...
```

Run it:

```bash
skipshit "https://www.youtube.com/watch?v=abc123" --avoid "crypto" --avoid "US politics"
```

### LLM Providers

**OpenRouter** (default) — Use any model available on OpenRouter. Models are specified in `provider/model` format:

```bash
skipshit "https://youtube.com/watch?v=abc123" --avoid "crypto" --model "anthropic/claude-sonnet-4"
```

**Anthropic** — Use the Anthropic API directly. Auto-detected when the model name doesn't contain a slash, or set explicitly with `--provider`:

```bash
skipshit "https://youtube.com/watch?v=abc123" --avoid "crypto" --model "claude-sonnet-4-20250514" --provider anthropic
```

### Options

```
skipshit <youtube_url> --avoid "topic1" --avoid "topic2" [options]

Options:
  --avoid, -a       Topic to skip (repeatable)
  --config, -c      Path to YAML config file with saved topics
  --output, -o      Output file path (default: stdout)
  --format, -f      Output format: json, text (default: json)
  --buffer          Buffer seconds around flagged segments (default: 30)
  --model           LLM model to use (default: openai/gpt-5-nano)
  --provider        LLM provider: openrouter, anthropic (auto-detected from model)
  --verbose, -v     Show progress and debug info
```

### Config file

Save your avoid-topics to `~/.config/skipshit/config.yaml` so you don't have to re-type them:

```yaml
avoid_topics:
  - "crypto"
  - "US politics"
  - "iDubbbz"

# Optional: set your provider and model
model: openai/gpt-5-nano
```

Config file search order:
1. `--config` path (if specified)
2. `$XDG_CONFIG_HOME/skipshit/config.yaml` (defaults to `~/.config/skipshit/config.yaml`)
3. `~/.skipshit.yaml` (legacy fallback)

With a config file, you can just run:

```bash
skipshit "https://www.youtube.com/watch?v=abc123" --format text
```

### Output formats

**JSON** (default):

```json
{
  "video_url": "https://www.youtube.com/watch?v=abc123",
  "video_title": "H3 Podcast #247",
  "skip_segments": [
    {
      "start": "0:46:14",
      "end": "1:29:36",
      "reason": "iDubbbz's comments about Ethan are discussed",
      "matched_topics": ["iDubbbz"],
      "confidence": "high"
    }
  ]
}
```

**Text** (`--format text`):

```
Skip Segments for "H3 Podcast #247":

  1. [0:46:14 → 1:29:36] iDubbbz's comments about Ethan are discussed
     Topics: iDubbbz | Confidence: high

Total skip time: 43 min 22 sec (of 3 hr 0 min)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
