"""Image generation, editing, background removal, thumbnails, diagrams, and passport photo sheets."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
import textwrap
from typing import Any

from google import genai
from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, ImageOps

from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        r"C:\Windows\Fonts\seguisb.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


class ImageStudio:
    """Multi-provider AI image studio + zero-cost local design/passport workflows."""

    def __init__(
        self,
        outputs_dir: Path,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.images_dir = (outputs_dir / "images").resolve()
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = permissions
        self.audit_logger = audit_logger

    def _out_path(self, prefix: str, ext: str = "png") -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:20]
        return self.images_dir / f"{prefix}_{stamp}.{ext}"

    async def generate_image(
        self,
        prompt: str,
        provider: str = "gemini",
        aspect_ratio: str = "1:1",
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
    ) -> dict[str, Any]:
        """Generate an image using Gemini Nano Banana 2.1, OpenAI, or explicit local canvas."""
        self.permissions.require(Permission.WRITE, f"Save generated image ({provider})", category="media")
        if provider == "local-canvas":
            return self.create_poster_or_thumbnail(
                title=prompt[:60],
                subtitle="ASPIRANT AI Local Design",
                aspect_ratio=aspect_ratio,
            )

        self.permissions.require(Permission.NETWORK, f"Generate image via {provider}", category="media")

        if provider in ("gemini", "auto"):
            if not gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for Gemini Nano Banana image generation.")
            client = genai.Client(api_key=gemini_api_key)
            interaction = await client.aio.interactions.create(
                model="gemini-nano-banana-2.1",
                input=prompt,
                response_format={
                    "type": "image",
                    "aspect_ratio": aspect_ratio,
                    "image_size": "1K",
                },
                store=False,
            )
            out_img = getattr(interaction, "output_image", None)
            if not out_img or not getattr(out_img, "data", None):
                raise RuntimeError("Gemini Nano Banana did not return an image.")
            out_path = self._out_path("gemini_img", "png")
            out_path.write_bytes(base64.b64decode(out_img.data))
            self.audit_logger.log(
                category="media",
                action=f"Generated image via Nano Banana 2.1 -> {out_path.name}",
                permission="NETWORK",
                decision="executed",
                status="ok",
            )
            return {"path": str(out_path), "provider": "gemini", "model": "gemini-nano-banana-2.1", "status": "completed"}

        if provider == "openai":
            if not openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI image generation.")
            client = AsyncOpenAI(api_key=openai_api_key)
            size = "1024x1024" if aspect_ratio == "1:1" else ("1792x1024" if aspect_ratio == "16:9" else "1024x1792")
            res = await client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
            b64 = res.data[0].b64_json if res.data else None
            if not b64:
                raise RuntimeError("OpenAI image generation returned no image data.")
            out_path = self._out_path("openai_img", "png")
            out_path.write_bytes(base64.b64decode(b64))
            return {"path": str(out_path), "provider": "openai", "model": "gpt-image-1", "status": "completed"}

        raise ValueError(f"Unknown image provider: {provider}")

    async def edit_image(
        self,
        image_path: str,
        edit_prompt: str,
        gemini_api_key: str | None,
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"Read image {image_path}", category="media")
        self.permissions.require(Permission.WRITE, "Save edited image", category="media")
        self.permissions.require(Permission.NETWORK, "Edit image via Gemini Nano Banana", category="media")
        if not gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for AI image editing.")

        src = Path(image_path).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Image not found: {src}")
        b64 = base64.b64encode(src.read_bytes()).decode("ascii")
        mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"

        client = genai.Client(api_key=gemini_api_key)
        interaction = await client.aio.interactions.create(
            model="gemini-nano-banana-2.1",
            input=[
                {"type": "text", "text": edit_prompt},
                {"type": "image", "data": b64, "mime_type": mime},
            ],
            response_format={"type": "image"},
            store=False,
        )
        out_img = getattr(interaction, "output_image", None)
        if not out_img or not getattr(out_img, "data", None):
            raise RuntimeError("Image editing provider returned no output image.")
        out_path = self._out_path("edited_img", "png")
        out_path.write_bytes(base64.b64decode(out_img.data))
        return {"path": str(out_path), "status": "completed", "provider": "gemini"}

    def remove_background_local(self, image_path: str, tolerance: int = 38) -> dict[str, Any]:
        """Remove solid/uniform corner-sampled background locally into transparent RGBA PNG."""
        self.permissions.require(Permission.READ, f"Read image {image_path}", category="media")
        self.permissions.require(Permission.WRITE, "Save transparent background cutout", category="media")
        src = Path(image_path).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Image not found: {src}")

        img = Image.open(src).convert("RGBA")
        w, h = img.size
        pixels = img.load()
        corners = [pixels[0, 0][:3], pixels[w - 1, 0][:3], pixels[0, h - 1][:3], pixels[w - 1, h - 1][:3]]
        bg_r = sum(c[0] for c in corners) // 4
        bg_g = sum(c[1] for c in corners) // 4
        bg_b = sum(c[2] for c in corners) // 4

        tol_sq = tolerance * tolerance * 3
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                dist_sq = (r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2
                if dist_sq <= tol_sq:
                    pixels[x, y] = (r, g, b, 0)

        out_path = self._out_path("nobg", "png")
        img.save(out_path, format="PNG")
        return {"path": str(out_path), "width": w, "height": h, "status": "completed"}

    def create_poster_or_thumbnail(
        self,
        title: str,
        subtitle: str = "",
        aspect_ratio: str = "16:9",
        accent_hex: str = "#7C3AED",
    ) -> dict[str, Any]:
        """Render a crisp gradient thumbnail, poster, or social design locally."""
        self.permissions.require(Permission.WRITE, "Create local poster/thumbnail", category="media")
        dims = {
            "16:9": (1280, 720),
            "9:16": (1080, 1920),
            "1:1": (1080, 1080),
            "4:5": (1080, 1350),
        }
        w, h = dims.get(aspect_ratio, (1280, 720))
        img = Image.new("RGB", (w, h), (10, 14, 30))
        draw = ImageDraw.Draw(img)

        # Smooth diagonal vertical gradient
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(12 + 24 * t)
            g = int(16 + 18 * (1 - t))
            b = int(38 + 42 * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Accent frame & glowing stripe
        draw.rectangle([36, 36, w - 36, h - 36], outline=accent_hex, width=4)
        draw.rectangle([64, 64, 300, 74], fill="#22D3EE")

        title_font = _load_font(max(36, w // 18))
        sub_font = _load_font(max(22, w // 32))
        wrapped = textwrap.fill(title.strip() or "ASPIRANT AI", width=22)
        draw.multiline_text((68, h // 3), wrapped, fill="#FFFFFF", font=title_font, spacing=14)
        if subtitle:
            draw.multiline_text((68, (h // 3) + 220), textwrap.fill(subtitle, width=36), fill="#94A3B8", font=sub_font, spacing=8)

        out_path = self._out_path("design", "png")
        img.save(out_path, format="PNG")
        return {"path": str(out_path), "width": w, "height": h, "aspect_ratio": aspect_ratio, "status": "completed"}

    def create_diagram_infographic(self, title: str, steps: list[str]) -> dict[str, Any]:
        """Render a clean educational workflow diagram / infographic PNG locally."""
        self.permissions.require(Permission.WRITE, "Create educational diagram", category="media")
        items = [s.strip() for s in steps if s.strip()][:8] or ["Input", "Process", "Output"]
        w = 1280
        h = max(620, 180 + len(items) * 105)
        img = Image.new("RGB", (w, h), (11, 16, 32))
        draw = ImageDraw.Draw(img)

        t_font = _load_font(40)
        s_font = _load_font(26)
        draw.text((60, 44), title.strip() or "Educational Diagram", fill="#22D3EE", font=t_font)

        y = 130
        for idx, step in enumerate(items, start=1):
            draw.rounded_rectangle([80, y, w - 80, y + 74], radius=14, fill=(24, 34, 62), outline="#7C3AED", width=3)
            draw.text((110, y + 20), f"{idx}. {step[:70]}", fill="#F8FAFC", font=s_font)
            if idx < len(items):
                cx = w // 2
                draw.line([(cx, y + 74), (cx, y + 102)], fill="#22D3EE", width=4)
            y += 102

        out_path = self._out_path("diagram", "png")
        img.save(out_path, format="PNG")
        return {"path": str(out_path), "width": w, "height": h, "steps": len(items), "status": "completed"}

    def create_passport_photo_sheet(
        self,
        portrait_path: str,
        copies: int = 8,
        bg_rgb: tuple[int, int, int] = (255, 255, 255),
    ) -> dict[str, Any]:
        """Crop to 35x45mm @ 300 DPI (413x531 px) and tile onto a 6x4 inch (1800x1200 px) print sheet."""
        self.permissions.require(Permission.READ, f"Read portrait {portrait_path}", category="media")
        self.permissions.require(Permission.WRITE, "Save printable passport photo sheet", category="media")
        src = Path(portrait_path).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Portrait image not found: {src}")

        passport_w, passport_h = 413, 531  # 35mm x 45mm at 300 DPI
        sheet_w, sheet_h = 1800, 1200       # 6in x 4in at 300 DPI

        raw = Image.open(src).convert("RGBA")
        fitted = ImageOps.fit(raw, (passport_w, passport_h), method=Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (passport_w, passport_h), bg_rgb)
        tile.paste(fitted, (0, 0), fitted)

        sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        cols, rows = 4, 2
        margin_x = (sheet_w - cols * passport_w) // (cols + 1)
        margin_y = (sheet_h - rows * passport_h) // (rows + 1)

        count = max(1, min(copies, 8))
        placed = 0
        for r in range(rows):
            for c in range(cols):
                if placed >= count:
                    break
                x = margin_x + c * (passport_w + margin_x)
                y = margin_y + r * (passport_h + margin_y)
                sheet.paste(tile, (x, y))
                draw.rectangle([x - 1, y - 1, x + passport_w, y + passport_h], outline=(200, 200, 200), width=1)
                placed += 1

        out_path = self._out_path("passport_sheet_300dpi", "png")
        sheet.save(out_path, format="PNG", dpi=(300, 300))
        return {
            "path": str(out_path),
            "sheet_size": [sheet_w, sheet_h],
            "photo_size_300dpi": [passport_w, passport_h],
            "copies": placed,
            "status": "completed",
        }
