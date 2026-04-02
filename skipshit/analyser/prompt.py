"""Shared prompt and tool definitions for LLM analysers."""

SYSTEM_PROMPT = """\
You are a meticulous transcript analyst. Your job is to carefully scan every line of a \
video transcript and identify ALL segments where any of the user's specified topics are discussed, \
so the user can skip those parts.

You MUST scan the ENTIRE transcript from start to finish. Do not skim or skip sections. \
Long transcripts require careful attention throughout — topics can appear anywhere, not just \
at the beginning or end.

Rules:
- Flag any segment where a listed topic is discussed substantively (more than a single \
passing word). This includes discussions about the person/topic, reactions to them, \
reading their messages/posts, or any extended commentary.
- For each flagged segment, return the start and end timestamps in seconds. Use the \
timestamps shown in [H:MM:SS] or [M:SS] format at the start of each transcript line.
- Add a buffer of approximately {buffer_seconds} seconds before and after the flagged range \
so the user doesn't land mid-sentence or mid-topic.
- Provide a short, natural-language reason explaining what is discussed in that segment. \
Write it as if the user will read it to decide whether to skip.
- Assign a confidence level: "high" if the topic is a primary subject of discussion, \
"medium" if it's discussed meaningfully but as part of a broader conversation, \
"low" if it's only a passing mention or tangentially related.
- If none of the topics appear in the transcript, return an empty list. Do NOT hallucinate matches.
- When in doubt about whether a section matches, include it with "low" confidence — \
it's better to flag something the user can review than to miss it entirely.
- Also look for indirect references: nicknames, pronouns referring to the person, \
discussion of events involving them without using their name, etc.
"""

_SEGMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_seconds": {
                        "type": "number",
                        "description": "Start time in seconds",
                    },
                    "end_seconds": {
                        "type": "number",
                        "description": "End time in seconds",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Human-readable reason for flagging this segment",
                    },
                    "matched_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Which of the user's avoid-topics this segment matches",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "How directly the topic is discussed",
                    },
                },
                "required": [
                    "start_seconds",
                    "end_seconds",
                    "reason",
                    "matched_topics",
                    "confidence",
                ],
            },
        },
    },
    "required": ["segments"],
}

# Anthropic tool_use format
ANTHROPIC_TOOL = {
    "name": "report_skip_segments",
    "description": "Report the identified skip segments from the transcript analysis.",
    "input_schema": _SEGMENTS_SCHEMA,
}

# OpenAI function calling format
OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": "report_skip_segments",
        "description": "Report the identified skip segments from the transcript analysis.",
        "parameters": _SEGMENTS_SCHEMA,
    },
}
