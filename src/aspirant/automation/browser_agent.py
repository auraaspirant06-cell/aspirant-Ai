"""Isolated Microsoft Edge browser automation via Playwright (zero personal cookie access)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager


def is_safe_browser_url(url: str) -> bool:
    """Allow only http/https navigation; block file:// and dangerous browser schemes."""
    parsed = urlparse(url.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


class IsolatedBrowserAgent:
    """Manages an isolated Microsoft Edge Playwright context under data/browser_profile."""

    def __init__(
        self,
        profile_dir: Path,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.profile_dir = profile_dir.resolve()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.permissions = permissions
        self.audit_logger = audit_logger
        self._playwright: Any = None
        self._context: Any = None

    async def _ensure_context(self, headless: bool = False) -> Any:
        if self._context is not None:
            return self._context
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="msedge",
            headless=headless,
        )
        return self._context

    async def open_tab(self, url: str, headless: bool = False) -> dict[str, Any]:
        self.permissions.require(Permission.BROWSER, f"Open browser tab {url}", category="browser")
        self.permissions.require(Permission.NETWORK, f"Navigate browser to {url}", category="browser")
        if not is_safe_browser_url(url):
            raise ValueError(f"Only http:// or https:// URLs are permitted (got {url!r}).")

        ctx = await self._ensure_context(headless=headless)
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        title = await page.title()
        self.audit_logger.log(
            category="browser",
            action=f"Opened isolated Edge tab: {url}",
            permission="BROWSER",
            decision="executed",
            status="ok",
        )
        return {"url": page.url, "title": title, "tab_count": len(ctx.pages)}

    async def list_tabs(self) -> list[dict[str, Any]]:
        self.permissions.require(Permission.BROWSER, "List isolated browser tabs", category="browser")
        if self._context is None:
            return []
        tabs: list[dict[str, Any]] = []
        for idx, page in enumerate(self._context.pages):
            try:
                title = await page.title()
            except Exception:
                title = ""
            tabs.append({"index": idx, "url": page.url, "title": title})
        return tabs

    async def close_tab(self, index: int) -> dict[str, Any]:
        self.permissions.require(Permission.BROWSER, f"Close browser tab #{index}", category="browser")
        if self._context is None or index < 0 or index >= len(self._context.pages):
            raise IndexError("Tab index out of range.")
        await self._context.pages[index].close()
        return {"closed": index, "remaining": len(self._context.pages)}

    async def close_all(self) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
