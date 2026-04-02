"""Tests for the analyser module using fixture data."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from skipshit.analyser.claude import ClaudeAnalyser, _parse_tool_response
from skipshit.models import Transcript, TranscriptSegment


MOCK_TOOL_RESPONSE = {
    "segments": [
        {
            "start_seconds": 55.0,
            "end_seconds": 78.0,
            "reason": "Discussion of cryptocurrency investments and altcoin recommendations",
            "matched_topics": ["crypto"],
            "confidence": "high",
        }
    ]
}


class TestParseToolResponse:
    def test_valid_response(self):
        result = _parse_tool_response(MOCK_TOOL_RESPONSE)
        assert len(result) == 1
        assert result[0].start_seconds == 55.0
        assert result[0].end_seconds == 78.0
        assert result[0].matched_topics == ["crypto"]
        assert result[0].confidence == "high"

    def test_empty_segments(self):
        result = _parse_tool_response({"segments": []})
        assert result == []

    def test_malformed_segment_skipped(self):
        bad_response = {
            "segments": [
                {"start_seconds": 10},  # missing required fields
                {
                    "start_seconds": 55.0,
                    "end_seconds": 78.0,
                    "reason": "test",
                    "matched_topics": ["crypto"],
                    "confidence": "high",
                },
            ]
        }
        result = _parse_tool_response(bad_response)
        assert len(result) == 1


class TestClaudeAnalyser:
    def test_analyse_calls_api(self, sample_transcript: Transcript):
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "report_skip_segments"
        mock_block.input = MOCK_TOOL_RESPONSE

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        with patch("skipshit.analyser.claude.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            analyser = ClaudeAnalyser(api_key="test-key")
            result = analyser.analyse(sample_transcript, ["crypto"])

        assert len(result.skip_segments) == 1
        assert result.skip_segments[0].matched_topics == ["crypto"]
        assert result.video_url == "https://www.youtube.com/watch?v=test123"
        assert result.metadata["transcript_source"] == "youtube_captions"
