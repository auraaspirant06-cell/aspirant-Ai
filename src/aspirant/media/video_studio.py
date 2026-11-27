"""AI Video Studio: Prompt -> Script -> Storyboard -> Scenes -> Voiceover -> Subtitles -> MP4."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any

from google import genai

from aspirant.media.ffmpeg_composer import compose_storyboard_mp4, render_scene_frame
from aspirant.media.subtitles import CaptionCue, write_srt
from aspirant.personality.language_detect import detect_language
from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.providers.tts_providers import TTSRouter
from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager
from aspirant.voice.profiles import VoiceConfig


def _split_script_to_scenes(prompt: str, script_text: str, max_scenes: int = 4) -> list[dict[str, str]]:
    """Parse structured script lines into clean storyboard beats."""
    lines = [ln.strip("-* \t") for ln in script_text.splitlines() if ln.strip()]
    if not lines:
        lines = [prompt.strip()]
    scenes: list[dict[str, str]] = []
    for idx, line in enumerate(lines[:max_scenes], start=1):
        scenes.append(
            {
                "scene": idx,
                "narration": line[:220],
                "visual": f"Visual Scene {idx}: {line[:140]}",
            }
        )
    return scenes


class VideoStudio:
    """Orchestrates generative AI video (Gemini Omni) and storyboard MP4 video creation."""

    def __init__(
        self,
        outputs_dir: Path,
        providers: ProviderRegistry,
        tts_router: TTSRouter,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.videos_dir = (outputs_dir / "videos").resolve()
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.providers = providers
        self.tts_router = tts_router
        self.permissions = permissions
        self.audit_logger = audit_logger

    async def generate_generative_clip(
        self,
        prompt: str,
        gemini_api_key: str | None,
        aspect_ratio: str = "9:16",
        first_frame_path: str | None = None,
        duration_sec: int = 6,
    ) -> dict[str, Any]:
        """Generate AI video via gemini-omni-1.2-flash.

        NEVER claims completion unless the provider returns valid video bytes.
        """
        self.permissions.require(Permission.WRITE, "Save generated video", category="media")
        self.permissions.require(Permission.NETWORK, "Call Gemini Omni 1.2 Flash video API", category="media")

        if not gemini_api_key:
            return {
                "status": "failed",
                "error": "GEMINI_API_KEY is not configured. Video was NOT generated.",
                "provider": "gemini-omni-1.2-flash",
            }

        ratio = aspect_ratio if aspect_ratio in {"9:16", "16:9"} else "16:9"
        client = genai.Client(api_key=gemini_api_key)

        input_payload: Any = prompt
        if first_frame_path:
            img_p = Path(first_frame_path).expanduser().resolve()
            if not img_p.is_file():
                return {"status": "failed", "error": f"First-frame image not found: {img_p}"}
            b64 = base64.b64encode(img_p.read_bytes()).decode("ascii")
            mime = "image/png" if img_p.suffix.lower() == ".png" else "image/jpeg"
            input_payload = [
                {"type": "image", "data": b64, "mime_type": mime},
                {"type": "text", "text": f"Use this image as the starting frame. {prompt}"},
            ]

        try:
            interaction = await client.aio.interactions.create(
                model="gemini-omni-1.2-flash",
                input=input_payload,
                response_format={"type": "video", "aspect_ratio": ratio},
                generation_config={"video_config": {"duration_seconds": max(3, min(15, duration_sec))}},
                store=False,
            )
            out_vid = getattr(interaction, "output_video", None)
            if not out_vid or not getattr(out_vid, "data", None):
                return {
                    "status": "failed",
                    "error": "Provider returned empty output_video; no video file produced.",
                    "provider": "gemini-omni-1.2-flash",
                }
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out_mp4 = self.videos_dir / f"omni_{stamp}.mp4"
            raw = base64.b64decode(out_vid.data)
            if len(raw) < 100:
                return {"status": "failed", "error": "Returned video payload was invalid/empty."}
            out_mp4.write_bytes(raw)
            self.audit_logger.log(
                category="media",
                action=f"Generated Gemini Omni video -> {out_mp4.name}",
                permission="NETWORK",
                decision="executed",
                status="ok",
            )
            return {
                "status": "completed",
                "provider": "gemini-omni-1.2-flash",
                "path": str(out_mp4),
                "aspect_ratio": ratio,
                "bytes": len(raw),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "provider": "gemini-omni-1.2-flash",
                "error": f"Generative video failed (not created): {exc}",
            }

    async def create_storyboard_video(
        self,
        prompt: str,
        video_style: str = "explainer",
        aspect_ratio: str = "9:16",
        script_override: str | None = None,
        include_voiceover: bool = True,
        bg_music_path: str | None = None,
    ) -> dict[str, Any]:
        """Execute full Prompt -> Script -> Storyboard -> Scenes -> Voiceover -> Subtitles -> MP4 pipeline."""
        self.permissions.require(Permission.WRITE, "Render storyboard MP4 video", category="media")

        lang_code = detect_language(script_override or prompt).code
        # Step 1 & 2: Script generation
        script_text = (script_override or "").strip()
        if not script_text:
            allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
            try:
                resp = await self.providers.generate(
                    ChatRequest(
                        messages=[
                            ChatMessage(
                                "user",
                                f"Write a short 3-4 line spoken narration script ({video_style} style, {aspect_ratio}) "
                                f"in the same language as this prompt:\n{prompt}\n"
                                "Return 3 to 4 crisp lines, one scene per line.",
                            )
                        ],
                        temperature=0.7,
                        max_tokens=300,
                    ),
                    allow_cloud=allow_cloud,
                )
                script_text = resp.text.strip()
            except Exception:
                # Deterministic offline storyboard fallback
                script_text = (
                    f"{prompt.strip()}\n"
                    f"Let us explore the key concepts step by step.\n"
                    f"Summary and next steps with ASPIRANT AI."
                )

        # Step 3: Storyboard
        scenes = _split_script_to_scenes(prompt, script_text, max_scenes=4)
        full_narration = " ".join(s["narration"] for s in scenes)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:20]
        out_mp4 = self.videos_dir / f"storyboard_{stamp}.mp4"
        srt_path = self.videos_dir / f"storyboard_{stamp}.srt"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Step 4: Scene Visuals
            scene_inputs: list[tuple[Path, float]] = []
            cues: list[CaptionCue] = []
            t_cursor = 0.0
            for idx, sc in enumerate(scenes, start=1):
                dur = max(2.2, min(6.0, len(sc["narration"].split()) * 0.45))
                png = render_scene_frame(
                    title=prompt[:60],
                    narration=sc["narration"],
                    visual_caption=sc["visual"],
                    scene_num=idx,
                    total_scenes=len(scenes),
                    aspect_ratio=aspect_ratio,
                    out_png=td_path / f"scene_{idx}.png",
                )
                scene_inputs.append((png, dur))
                cues.append(CaptionCue(index=idx, start_sec=t_cursor, end_sec=t_cursor + dur, text=sc["narration"]))
                t_cursor += dur

            # Step 5: Female AI Voiceover
            vo_path: Path | None = None
            vo_provider = "none"
            if include_voiceover:
                allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
                tts_res = await self.tts_router.synthesize(
                    full_narration,
                    language_code=lang_code,
                    config=VoiceConfig(tts_provider="auto", emotion="friendly"),
                    allow_cloud=allow_cloud,
                )
                ext = "wav" if "wav" in tts_res.mime_type else "mp3"
                vo_path = td_path / f"voiceover.{ext}"
                vo_path.write_bytes(tts_res.audio_bytes)
                vo_provider = f"{tts_res.provider} ({tts_res.voice_name})"

            # Step 6: Subtitles
            write_srt(cues, srt_path)

            # Step 7 & 8: Editing & Final MP4 Export
            bg_p = Path(bg_music_path).expanduser().resolve() if bg_music_path else None
            render_info = compose_storyboard_mp4(
                scene_images=scene_inputs,
                voiceover_audio=vo_path,
                srt_path=srt_path,
                out_mp4=out_mp4,
                bg_music_audio=bg_p,
            )

        self.audit_logger.log(
            category="media",
            action=f"Rendered {aspect_ratio} storyboard MP4 -> {out_mp4.name}",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {
            "status": "completed",
            "mode": "storyboard-local",
            "style": video_style,
            "aspect_ratio": aspect_ratio,
            "language": lang_code,
            "script": script_text,
            "storyboard": scenes,
            "voiceover": vo_provider,
            "srt_path": str(srt_path),
            "path": render_info["mp4_path"],
            "bytes": render_info["bytes"],
        }
