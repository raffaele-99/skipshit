# Adding Providers

## Adding a New Transcript Source

To add a new way of fetching transcripts (e.g. Whisper, a podcast API):

1. Create a new file in `skipshit/transcript/`, e.g. `whisper.py`
2. Implement the `TranscriptFetcher` abstract base class:

```python
from skipshit.transcript.base import TranscriptFetcher
from skipshit.models import Transcript, TranscriptSegment


class WhisperFetcher(TranscriptFetcher):
    def fetch(self, video_id: str) -> Transcript:
        # Download audio, run Whisper, build segments
        segments = [
            TranscriptSegment(
                text="transcribed text",
                start_seconds=0.0,
                duration_seconds=5.0,
            )
        ]
        return Transcript(
            video_id=video_id,
            segments=segments,
            source="whisper",
        )
```

3. Optionally add it to the fallback chain in `skipshit/transcript/__init__.py`:

```python
from skipshit.transcript.whisper import WhisperFetcher

def get_transcript(url: str, language: str = "en") -> Transcript:
    video_id = YouTubeCaptionsFetcher.extract_video_id(url)
    # ... existing fetchers ...
    fallback2 = WhisperFetcher()
    return fallback2.fetch(video_id)
```

The key contract: your fetcher must return a `Transcript` with a list of `TranscriptSegment` objects, each having `text`, `start_seconds`, and `duration_seconds`.

## Adding a New LLM Provider

skipshit ships with two LLM analysers:

- **`OpenRouterAnalyser`** (`analyser/openrouter.py`) — Uses the OpenAI-compatible API to access any model on OpenRouter. This is the default.
- **`ClaudeAnalyser`** (`analyser/claude.py`) — Uses the Anthropic SDK directly.

Both share the same system prompt and tool schema defined in `analyser/prompt.py`.

### Using an OpenAI-compatible API

If your provider exposes an OpenAI-compatible API (e.g. Together, Groq, a local vLLM server), the easiest path is to subclass or modify `OpenRouterAnalyser` and change `OPENROUTER_BASE_URL`:

```python
from skipshit.analyser.openrouter import OpenRouterAnalyser

class TogetherAnalyser(OpenRouterAnalyser):
    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3-70b"):
        super().__init__(api_key=api_key, model=model)
        self.client.base_url = "https://api.together.xyz/v1"
```

### Building from scratch

To add a provider with a different API format:

1. Create a new file in `skipshit/analyser/`, e.g. `my_provider.py`
2. Implement the `TopicAnalyser` abstract base class:

```python
from skipshit.analyser.base import TopicAnalyser, ChunkConfig
from skipshit.analyser.chunker import chunk_transcript
from skipshit.analyser.merger import merge_skip_segments
from skipshit.analyser.prompt import SYSTEM_PROMPT
from skipshit.models import AnalysisResult, SkipSegment, Transcript


class MyProviderAnalyser(TopicAnalyser):
    def __init__(self, api_key: str, model: str = "my-model"):
        self.api_key = api_key
        self.model = model

    def analyse(
        self,
        transcript: Transcript,
        topics: list[str],
        chunk_config: ChunkConfig | None = None,
    ) -> AnalysisResult:
        config = chunk_config or ChunkConfig()
        chunks = chunk_transcript(transcript, max_tokens=config.max_tokens)

        all_segments = []
        for chunk in chunks:
            # Use SYSTEM_PROMPT.format(buffer_seconds=config.buffer_seconds)
            # Send chunk to your LLM, parse response into SkipSegments
            segments = self._analyse_chunk(chunk, topics, config.buffer_seconds)
            all_segments.extend(segments)

        merged = merge_skip_segments(all_segments)
        return AnalysisResult(
            video_url=f"https://www.youtube.com/watch?v={transcript.video_id}",
            video_title=transcript.video_title,
            duration_seconds=transcript.duration_seconds,
            skip_segments=merged,
            metadata={"model_used": self.model},
        )
```

3. Wire it into `cli.py` by adding a case to `_build_analyser()`:

```python
def _build_analyser(provider: str, api_key: str, model: str) -> TopicAnalyser:
    if provider == "openrouter":
        from skipshit.analyser.openrouter import OpenRouterAnalyser
        return OpenRouterAnalyser(api_key=api_key, model=model)
    elif provider == "my_provider":
        from skipshit.analyser.my_provider import MyProviderAnalyser
        return MyProviderAnalyser(api_key=api_key, model=model)
    else:
        from skipshit.analyser.claude import ClaudeAnalyser
        return ClaudeAnalyser(api_key=api_key, model=model)
```

4. Add the provider name to the `--provider` click.Choice in `cli.py` and the `_infer_provider()` logic in `config.py`.

### Reusing shared components

The chunker, merger, and prompt are all provider-agnostic — reuse them:

- **`analyser/prompt.py`** — Import `SYSTEM_PROMPT` for the system prompt. It has a `{buffer_seconds}` placeholder. Import `OPENAI_TOOL` if your provider uses OpenAI-compatible function calling, or `ANTHROPIC_TOOL` for the Anthropic format. The tool schema defines the `report_skip_segments` function that returns structured skip segment data.
- **`analyser/chunker.py`** — `chunk_transcript()` splits the transcript into manageable pieces.
- **`analyser/merger.py`** — `merge_skip_segments()` deduplicates and consolidates overlapping results.

### Prompt tips

The shared prompt in `prompt.py` is the result of iteration. Key elements to preserve:
- Instruct the model to scan the **entire** transcript — models tend to skim long inputs
- Use structured output (tool use / function calling) rather than asking for JSON in prose
- Ask for a time buffer around flagged segments
- Explicitly tell the model not to hallucinate matches
- Request human-readable reasons
- Ask the model to look for indirect references (nicknames, pronouns, related events)
