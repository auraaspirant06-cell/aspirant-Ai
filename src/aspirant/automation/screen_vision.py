"""Screenshot capture and optional multimodal screen understanding."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from PIL import ImageGrab

from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager


class ScreenVisionEngine:
    """Explicit, audited screenshot capture and screen-content understanding."""

    def __init__(
        self,
        outputs_dir: Path,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.screenshots_dir = (outputs_dir / "screenshots").resolve()
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = permissions
        self.audit_logger = audit_logger

    def capture(self) -> dict[str, Any]:
        self.permissions.require(Permission.READ, "Capture desktop screenshot", category="screen")
        try:
            img = ImageGrab.grab()
        except OSError as exc:
            raise RuntimeError(
                f"Screen capture unavailable in current desktop session: {exc}"
            ) from exc
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = self.screenshots_dir / f"screen_{stamp}.png"
        img.save(out_path, format="PNG")
        self.audit_logger.log(
            category="screen",
            action=f"Captured screenshot {out_path.name}",
            permission="READ",
            decision="executed",
            status="ok",
        )
        return {
            "path": str(out_path),
            "width": img.width,
            "height": img.height,
        }

    async def understand_screen(
        self,
        question: str,
        gemini_api_key: str | None,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, "Analyze screen content", category="screen")
        self.permissions.require(Permission.NETWORK, "Send screenshot for multimodal vision analysis", category="screen")

        if not gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for multimodal screen understanding.")

        if image_path:
            target = Path(image_path).resolve()
        else:
            target = Path(self.capture()["path"])

        raw_b64 = base64.b64encode(target.read_bytes()).decode("ascii")
        client = genai.Client(api_key=gemini_api_key)
        resp = await client.aio.interactions.create(
            model="gemini-4-hydrogen",
            input=[
                {"type": "text", "text": question or "Describe the visible Windows screen and active UI clearly."},
                {"type": "image", "data": raw_b64, "mime_type": "image/png"},
            ],
            store=False,
        )
        return {
            "screenshot_path": str(target),
            "analysis": getattr(resp, "output_text", None) or "",
        }
