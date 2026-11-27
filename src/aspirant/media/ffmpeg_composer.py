"""FFmpeg storyboard video renderer using bundled imageio-ffmpeg binary."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import textwrap
from typing import Any

import imageio_ffmpeg
from PIL import Image, ImageDraw

from aspirant.media.image_studio import _load_font

ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}


def render_scene_frame(
    title: str,
    narration: str,
    visual_caption: str,
    scene_num: int,
    total_scenes: int,
    aspect_ratio: str,
    out_png: Path,
) -> Path:
    """Render a clean storyboard slide frame for local MP4 composition."""
    w, h = ASPECT_DIMENSIONS.get(aspect_ratio, (720, 1280))
    img = Image.new("RGB", (w, h), (9, 13, 28))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / max(1, h - 1)
        draw.line([(0, y), (w, y)], fill=(int(10 + 18 * t), int(14 + 14 * (1 - t)), int(34 + 40 * t)))

    draw.rectangle([28, 28, w - 28, h - 28], outline="#7C3AED", width=4)
    badge_font = _load_font(22)
    head_font = _load_font(max(28, w // 22))
    body_font = _load_font(max(22, w // 28))

    draw.text((52, 50), f"ASPIRANT AI • SCENE {scene_num}/{total_scenes}", fill="#22D3EE", font=badge_font)
    wrap_w = 24 if aspect_ratio == "9:16" else 38
    draw.multiline_text((52, 120), textwrap.fill(title, width=wrap_w), fill="#FFFFFF", font=head_font, spacing=10)

    # Visual box
    box_top = int(h * 0.34)
    box_bot = int(h * 0.64)
    draw.rounded_rectangle([52, box_top, w - 52, box_bot], radius=16, fill=(22, 30, 58), outline="#3B82F6", width=3)
    draw.multiline_text(
        (76, box_top + 28),
        textwrap.fill(visual_caption, width=wrap_w),
        fill="#CBD5E1",
        font=body_font,
        spacing=10,
    )

    # Caption footer
    draw.multiline_text(
        (52, int(h * 0.72)),
        textwrap.fill(narration, width=wrap_w + 4),
        fill="#F8FAFC",
        font=body_font,
        spacing=8,
    )
    img.save(out_png, format="PNG")
    return out_png


def compose_storyboard_mp4(
    scene_images: list[tuple[Path, float]],
    voiceover_audio: Path | None,
    srt_path: Path | None,
    out_mp4: Path,
    bg_music_audio: Path | None = None,
) -> dict[str, Any]:
    """Assemble scene images, female voiceover, optional bg music, and soft SRT captions into MP4."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        concat_file = Path(td) / "scenes.txt"
        lines: list[str] = []
        for img_path, dur in scene_images:
            safe_p = str(img_path.resolve()).replace("\\", "/")
            lines.append(f"file '{safe_p}'")
            lines.append(f"duration {max(1.5, dur):.2f}")
        # Repeat last image path per ffmpeg concat demuxer spec
        last_p = str(scene_images[-1][0].resolve()).replace("\\", "/")
        lines.append(f"file '{last_p}'")
        concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
        audio_inputs = 0
        if voiceover_audio and voiceover_audio.exists():
            cmd.extend(["-i", str(voiceover_audio)])
            audio_inputs += 1
        if bg_music_audio and bg_music_audio.exists():
            cmd.extend(["-stream_loop", "-1", "-i", str(bg_music_audio)])
            audio_inputs += 1
        if srt_path and srt_path.exists():
            cmd.extend(["-i", str(srt_path)])

        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24"])

        if audio_inputs == 2:
            cmd.extend(
                [
                    "-filter_complex",
                    "[1:a]volume=1.0[vo];[2:a]volume=0.16[bg];[vo][bg]amix=inputs=2:duration=first[aout]",
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                    "-c:a",
                    "aac",
                    "-shortest",
                ]
            )
            if srt_path and srt_path.exists():
                cmd.extend(["-map", "3:s", "-c:s", "mov_text"])
        elif audio_inputs == 1:
            cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"])
            if srt_path and srt_path.exists():
                cmd.extend(["-map", "2:s", "-c:s", "mov_text"])
        else:
            cmd.extend(["-map", "0:v"])
            if srt_path and srt_path.exists():
                cmd.extend(["-map", "1:s", "-c:s", "mov_text"])

        cmd.append(str(out_mp4))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0 or not out_mp4.exists() or out_mp4.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg render failed: {proc.stderr[-800:]}")

    return {"mp4_path": str(out_mp4), "bytes": out_mp4.stat().st_size}
