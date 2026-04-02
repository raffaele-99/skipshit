# Architecture

## Data Flow

```mermaid
graph LR
    A[YouTube URL] --> B[Transcript Fetcher]
    B --> C[Chunker]
    C --> D[LLM Analyser]
    D --> E[Merger]
    E --> F[Output JSON/Text]
```

```
URL → extract_video_id() → fetch transcript → chunk transcript → LLM analysis per chunk → merge results → format output
```

## Module Responsibilities

### `models.py`
The data contract layer. Defines all shared types (`Transcript`, `SkipSegment`, `AnalysisResult`, etc.) using Pydantic v2. Every other module depends on these types. No module depends on another module's internals — they communicate through models.

### `transcript/`
Responsible for fetching video transcripts. Two implementations behind a common `TranscriptFetcher` interface:

- **`YouTubeCaptionsFetcher`** — Primary. Uses `youtube-transcript-api` to pull captions directly. Fast and doesn't require downloading the video.
- **`YtDlpFetcher`** — Fallback. Uses `yt-dlp` to download subtitle files (VTT/SRT/JSON3) when the primary method fails (e.g. restricted videos, missing API captions).

The `__init__.py` exports `get_transcript()` which tries primary then fallback automatically.

### `analyser/prompt.py`
Shared system prompt and tool definitions used by all LLM analysers. The prompt is defined once and exported in both Anthropic tool_use format (`ANTHROPIC_TOOL`) and OpenAI function calling format (`OPENAI_TOOL`). This keeps the analysis behaviour consistent across providers.

### `analyser/chunker.py`
Splits a `Transcript` into `TranscriptChunk` objects that fit within LLM context windows. Uses a character-based token estimation heuristic (4 chars ≈ 1 token). Chunks overlap by a configurable number of seconds to avoid missing topics at boundaries. Default chunk size is 16k tokens — smaller chunks improve detection accuracy at a modest cost increase (~10% for a 4-hour video).

### `analyser/claude.py`
LLM analyser for the Anthropic API directly. Uses the Anthropic SDK with tool_use for structured output. Selected when `--provider anthropic` is set or the model name doesn't contain a slash.

### `analyser/openrouter.py`
LLM analyser for OpenRouter, which provides access to Claude and many other models via an OpenAI-compatible API. Uses the OpenAI SDK pointed at OpenRouter's base URL. Selected automatically when the model name contains a slash (e.g. `anthropic/claude-sonnet-4`), or when `--provider openrouter` is set.

### `analyser/merger.py`
Post-processing. Takes skip segments from all chunks and merges overlapping or adjacent segments (within a configurable gap). Keeps the most descriptive reason, unions topic lists, and promotes to the highest confidence level.

### `cli.py`
The user-facing entry point. Wires all modules together: parse args → load config → select provider → fetch transcript → analyse → format output. Uses `click` for argument parsing. Only module that configures logging or writes to stdout. Auto-detects the provider from the model name (slash = OpenRouter, no slash = Anthropic).

### `config.py`
Loads configuration from three layers (highest priority first): CLI arguments, environment variables (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `SKIPSHIT_API_KEY`, `SKIPSHIT_MODEL`, `SKIPSHIT_PROVIDER`), YAML config file. Centralises all configuration resolution so other modules just receive a `Config` object.

## Design Decisions

| Decision | Rationale |
|---|---|
| **Pydantic for models** | Provides validation, serialisation, and clear type contracts between modules. Catches malformed LLM responses early. |
| **Tool use / function calling for LLM output** | More reliable than asking the model to output JSON in prose. The API enforces the schema, reducing parse failures. Works across both Anthropic and OpenAI-compatible APIs. |
| **Shared prompt in `prompt.py`** | The system prompt and tool schema are defined once and exported in both Anthropic and OpenAI formats. Ensures consistent analysis behaviour regardless of provider. |
| **OpenRouter as default provider** | OpenRouter gives access to many models (including Claude) with a single API key, and most users don't have a direct Anthropic API key. The OpenAI-compatible API also makes it easy to add more providers later. |
| **16k default chunk size** | Smaller chunks (vs 80k) significantly improve topic detection accuracy. The model loses track of content buried in very large chunks. 16k adds ~10% token overhead for a 4-hour video but catches substantially more matches. |
| **Character-based token estimation** | Avoids adding a tokeniser dependency. The 4:1 ratio is conservative enough to avoid context window overflows. |
| **Overlap in chunks** | Topics discussed across chunk boundaries would be missed without overlap. 120s default is enough to capture most conversation transitions. |
| **Abstract base classes** | `TranscriptFetcher` and `TopicAnalyser` ABCs make it straightforward to add new providers without modifying existing code. |
| **No global state** | All dependencies are passed through constructors or function arguments. Makes testing easy and avoids hidden coupling. |
| **Logging, not printing** | Only `cli.py` configures output. Library modules use `logging` so consumers can control verbosity. |
