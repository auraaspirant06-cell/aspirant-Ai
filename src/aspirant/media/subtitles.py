"""SRT subtitle generator for Hindi, Hinglish, and English video captions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CaptionCue:
    index: int
    start_sec: float
    end_sec: float
    text: str


def _fmt_srt_time(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hrs = ms_total // 3_600_000
    mins = (ms_total % 3_600_000) // 60_000
    secs = (ms_total % 60_000) // 1000
    ms = ms_total % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def build_srt_content(cues: list[CaptionCue]) -> str:
    blocks: list[str] = []
    for cue in cues:
        blocks.append(
            f"{cue.index}\n"
            f"{_fmt_srt_time(cue.start_sec)} --> {_fmt_srt_time(cue.end_sec)}\n"
            f"{cue.text.strip()}\n"
        )
    return "\n".join(blocks)


def write_srt(cues: list[CaptionCue], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_srt_content(cues), encoding="utf-8")
    return out_path
