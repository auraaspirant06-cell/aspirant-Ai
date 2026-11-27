"""Phase 7 tests for Image Studio, Passport 300 DPI sheets, SRT captions, FFmpeg MP4 export, and Video honesty."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PIL import Image
from PySide6.QtWidgets import QApplication

from aspirant.core.config import AppSettings
from aspirant.providers.tts_providers import TTSResult
from aspirant.server.app import build_container, create_app
from aspirant.ui.views.image_view import ImageStudioView
from aspirant.ui.views.video_view import VideoStudioView
from aspirant.voice.audio_io import pcm16_to_wav_bytes
from aspirant.voice.profiles import VoiceConfig


def test_image_and_video_studios_end_to_end(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)

    # Deterministic audio stub so storyboard MP4 renders cleanly offline in test
    async def _fake_tts(text: str, language_code: str, config: VoiceConfig, allow_cloud: bool = True):
        return TTSResult(
            audio_bytes=pcm16_to_wav_bytes(b"\x00\x00" * 16000),  # 1 second silent WAV
            mime_type="audio/wav",
            voice_name="en-IN-NeerjaNeural",
            provider="edge-tts",
            latency_ms=2.0,
        )

    container.tts_router.synthesize = _fake_tts  # type: ignore[method-assign]
    app = create_app(settings=settings, container=container)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    # Create sample portrait with white background for passport & bg-removal tests
    portrait = tmp_path / "portrait.png"
    img = Image.new("RGB", (600, 700), (255, 255, 255))
    for y in range(200, 520):
        for x in range(200, 400):
            img.putpixel((x, y), (40, 80, 160))
    img.save(portrait)

    with client:
        client.post("/api/v1/system/permissions", headers=headers, json={"permission": "WRITE", "granted": True})

        # 1. Local Poster / Thumbnail & Diagram
        poster = client.post(
            "/api/v1/media/image/poster",
            headers=headers,
            json={"title": "Python Mastery", "subtitle": "Hindi Explainer", "aspect_ratio": "16:9"},
        )
        assert poster.status_code == 200
        p_path = Path(poster.json()["path"])
        assert p_path.exists()
        assert Image.open(p_path).size == (1280, 720)

        diag = client.post(
            "/api/v1/media/image/diagram",
            headers=headers,
            json={"title": "AI Pipeline", "steps": ["Prompt", "Script", "Voiceover", "MP4"]},
        )
        assert diag.status_code == 200
        assert Path(diag.json()["path"]).exists()

        # 2. Local Background Removal (transparent RGBA)
        nobg = client.post(
            "/api/v1/media/image/remove-bg",
            headers=headers,
            json={"image_path": str(portrait)},
        )
        assert nobg.status_code == 200
        out_nobg = Image.open(nobg.json()["path"])
        assert out_nobg.mode == "RGBA"
        assert out_nobg.getpixel((5, 5))[3] == 0

        # 3. Indian Passport Sheet (6x4 in 300 DPI = 1800x1200)
        sheet = client.post(
            "/api/v1/media/image/passport-sheet",
            headers=headers,
            json={"portrait_path": str(portrait), "copies": 8},
        )
        assert sheet.status_code == 200
        assert sheet.json()["sheet_size"] == [1800, 1200]
        assert sheet.json()["photo_size_300dpi"] == [413, 531]
        assert Path(sheet.json()["path"]).exists()

        # 4. Honest Generative Video failure when unconfigured
        gen_fail = client.post(
            "/api/v1/media/video/generative",
            headers=headers,
            json={"prompt": "Sunrise over Varanasi", "aspect_ratio": "9:16"},
        )
        assert gen_fail.status_code == 200
        assert gen_fail.json()["status"] == "failed"

        # 5. Real Storyboard -> Female Voiceover -> Bilingual SRT -> FFmpeg MP4 Export
        vid = client.post(
            "/api/v1/media/video/storyboard",
            headers=headers,
            json={
                "prompt": "Learn FastAPI in 60 seconds",
                "video_style": "reels",
                "aspect_ratio": "9:16",
                "script_override": "नमस्ते दोस्तों!\nFastAPI से आप तेज़ Python API बना सकते हैं।",
            },
        )
        assert vid.status_code == 200
        vdata = vid.json()
        assert vdata["status"] == "completed"
        assert Path(vdata["path"]).exists()
        assert Path(vdata["path"]).stat().st_size > 1000
        assert Path(vdata["srt_path"]).exists()
        assert "नमस्ते दोस्तों!" in Path(vdata["srt_path"]).read_text(encoding="utf-8")

    qt = QApplication.instance() or QApplication([])
    img_ui = ImageStudioView(api_client=None)  # type: ignore[arg-type]
    vid_ui = VideoStudioView(api_client=None)  # type: ignore[arg-type]
    assert img_ui.ratio_combo.count() == 4
    assert vid_ui.ratio_combo.count() == 3
    qt.processEvents()
