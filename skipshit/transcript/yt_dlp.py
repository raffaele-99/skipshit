"""Transcript fetcher using yt-dlp as a fallback."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path

from skipshit.models import Transcript, TranscriptSegment
from skipshit.transcript.base import TranscriptFetcher

logger = logging.getLogger(__name__)


class YtDlpFetcher(TranscriptFetcher):
    """Fetches transcripts by downloading subtitles via yt-dlp."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def fetch(self, video_id: str) -> Transcript:
        import yt_dlp

        logger.info("Fetching transcript for %s via yt-dlp", video_id)
        url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
            ydl_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [self.language],
                "subtitlesformat": "json3",
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            video_title = info.get("title")
            duration = info.get("duration")

            sub_files = list(Path(tmpdir).glob(f"*.{self.language}.*"))
            if not sub_files:
                sub_files = list(Path(tmpdir).glob("*.json3"))
            if not sub_files:
                sub_files = list(Path(tmpdir).glob("*.vtt"))
            if not sub_files:
                sub_files = list(Path(tmpdir).glob("*.srt"))

            if not sub_files:
                raise RuntimeError(
                    f"yt-dlp did not produce subtitle files for {video_id}"
                )

            sub_file = sub_files[0]
            suffix = sub_file.suffix.lower()
            content = sub_file.read_text(encoding="utf-8")

            if suffix == ".json3":
                segments = _parse_json3(content)
            elif suffix == ".vtt":
                segments = _parse_vtt(content)
            elif suffix == ".srt":
                segments = _parse_srt(content)
            else:
                raise RuntimeError(f"Unsupported subtitle format: {suffix}")

        if not segments:
            raise RuntimeError(
                f"No transcript segments parsed from yt-dlp output for {video_id}"
            )

        return Transcript(
            video_id=video_id,
            video_title=video_title,
            duration_seconds=duration,
            segments=segments,
            source="yt_dlp",
        )


def _parse_json3(content: str) -> list[TranscriptSegment]:
    data = json.loads(content)
    segments = []
    for event in data.get("events", []):
        start_ms = event.get("tStartMs", 0)
        duration_ms = event.get("dDurationMs", 0)
        segs = event.get("segs", [])
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if text and text != "\n":
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_seconds=start_ms / 1000.0,
                    duration_seconds=duration_ms / 1000.0,
                )
            )
    return segments


def _parse_vtt(content: str) -> list[TranscriptSegment]:
    segments = []
    blocks = content.split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        timestamp_line = None
        for line in lines:
            if "-->" in line:
                timestamp_line = line
                break
        if not timestamp_line:
            continue
        parts = timestamp_line.split("-->")
        start = _parse_vtt_time(parts[0].strip())
        end = _parse_vtt_time(parts[1].strip().split()[0])
        text_lines = []
        found_ts = False
        for line in lines:
            if found_ts:
                cleaned = re.sub(r"<[^>]+>", "", line).strip()
                if cleaned:
                    text_lines.append(cleaned)
            if "-->" in line:
                found_ts = True
        text = " ".join(text_lines)
        if text:
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_seconds=start,
                    duration_seconds=end - start,
                )
            )
    return segments


def _parse_srt(content: str) -> list[TranscriptSegment]:
    segments = []
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        timestamp_line = lines[1]
        parts = timestamp_line.split("-->")
        start = _parse_srt_time(parts[0].strip())
        end = _parse_srt_time(parts[1].strip())
        text = " ".join(line.strip() for line in lines[2:] if line.strip())
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_seconds=start,
                    duration_seconds=end - start,
                )
            )
    return segments


def _parse_vtt_time(time_str: str) -> float:
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    else:
        h = "0"
        m, s = parts
    seconds = float(h) * 3600 + float(m) * 60 + float(s.replace(",", "."))
    return seconds


def _parse_srt_time(time_str: str) -> float:
    return _parse_vtt_time(time_str.replace(",", "."))
