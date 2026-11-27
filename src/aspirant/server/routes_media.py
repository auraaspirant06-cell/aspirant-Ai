"""Modular FastAPI router for Image Studio and AI Video Studio (Phase 7)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aspirant.security.permissions import PermissionDeniedError


class ImageGenerateRequest(BaseModel):
    prompt: str
    provider: str = "gemini"
    aspect_ratio: str = "1:1"


class ImageEditRequest(BaseModel):
    image_path: str
    edit_prompt: str


class ImagePathRequest(BaseModel):
    image_path: str
    tolerance: int = 38


class PosterRequest(BaseModel):
    title: str
    subtitle: str = ""
    aspect_ratio: str = "16:9"
    accent_hex: str = "#7C3AED"


class DiagramRequest(BaseModel):
    title: str
    steps: list[str]


class PassportSheetRequest(BaseModel):
    portrait_path: str
    copies: int = 8


class VideoGenerativeRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "9:16"
    first_frame_path: str | None = None
    duration_sec: int = 6


class VideoStoryboardRequest(BaseModel):
    prompt: str
    video_style: str = "explainer"
    aspect_ratio: str = "9:16"
    script_override: str | None = None
    include_voiceover: bool = True
    bg_music_path: str | None = None


def create_media_router(container: Any, auth_dependency: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/media", dependencies=[auth_dependency])

    @router.post("/image/generate")
    async def generate_image(body: ImageGenerateRequest) -> dict[str, Any]:
        gkey = container.vault.get_secret("GEMINI_API_KEY") or container.settings.gemini_api_key
        okey = container.vault.get_secret("OPENAI_API_KEY") or container.settings.openai_api_key
        try:
            return await container.image_studio.generate_image(
                prompt=body.prompt,
                provider=body.provider,
                aspect_ratio=body.aspect_ratio,
                gemini_api_key=gkey,
                openai_api_key=okey,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/image/edit")
    async def edit_image(body: ImageEditRequest) -> dict[str, Any]:
        gkey = container.vault.get_secret("GEMINI_API_KEY") or container.settings.gemini_api_key
        try:
            return await container.image_studio.edit_image(body.image_path, body.edit_prompt, gkey)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/image/remove-bg")
    async def remove_bg(body: ImagePathRequest) -> dict[str, Any]:
        try:
            return container.image_studio.remove_background_local(body.image_path, tolerance=body.tolerance)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/image/poster")
    async def create_poster(body: PosterRequest) -> dict[str, Any]:
        try:
            return container.image_studio.create_poster_or_thumbnail(
                title=body.title,
                subtitle=body.subtitle,
                aspect_ratio=body.aspect_ratio,
                accent_hex=body.accent_hex,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/image/diagram")
    async def create_diagram(body: DiagramRequest) -> dict[str, Any]:
        try:
            return container.image_studio.create_diagram_infographic(body.title, body.steps)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/image/passport-sheet")
    async def passport_sheet(body: PassportSheetRequest) -> dict[str, Any]:
        try:
            return container.image_studio.create_passport_photo_sheet(body.portrait_path, copies=body.copies)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/video/generative")
    async def generative_video(body: VideoGenerativeRequest) -> dict[str, Any]:
        gkey = container.vault.get_secret("GEMINI_API_KEY") or container.settings.gemini_api_key
        try:
            return await container.video_studio.generate_generative_clip(
                prompt=body.prompt,
                gemini_api_key=gkey,
                aspect_ratio=body.aspect_ratio,
                first_frame_path=body.first_frame_path,
                duration_sec=body.duration_sec,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/video/storyboard")
    async def storyboard_video(body: VideoStoryboardRequest) -> dict[str, Any]:
        try:
            return await container.video_studio.create_storyboard_video(
                prompt=body.prompt,
                video_style=body.video_style,
                aspect_ratio=body.aspect_ratio,
                script_override=body.script_override,
                include_voiceover=body.include_voiceover,
                bg_music_path=body.bg_music_path,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return router
