"""End-to-end Playwright browser navigation verification across all 10 Next.js App Router pages."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

EXPECTED_SCREENS = [
    ("overview", "/", "Ecosystem Command Center"),
    ("nova", "/nova", "NOVA Desktop Operator"),
    ("mj", "/mj", "MJ Human Intelligence"),
    ("max", "/max", "MAX Mobile Companion"),
    ("voice", "/voice", "Voice Intelligence & Identity"),
    ("agents", "/agents", "Multi-Agent Reasoning Engine"),
    ("memory", "/memory", "Semantic Memory & Hybrid RAG"),
    ("integrations", "/integrations", "Social Platform Integrations"),
    ("security", "/security", "Zero-Trust Security & Self-Healing"),
    ("settings", "/settings", "Ecosystem Preferences & Settings"),
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_port(port: int, timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"Next.js server did not bind port {port} within {timeout}s")


async def run_nav_checks(base_url: str) -> dict:
    console_errors: list[str] = []
    page_errors: list[str] = []
    visited: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1366, "height": 840})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(base_url, wait_until="networkidle")

        for route_id, href, expected_title in EXPECTED_SCREENS:
            nav_selector = f'nav a[data-route-id="{route_id}"]'
            await page.locator(nav_selector).click()
            await page.wait_for_url(f"{base_url}{href}" if href != "/" else f"{base_url}/")
            await page.wait_for_selector(f'[data-screen-id="{route_id}"]')

            screen_id = await page.locator("[data-screen-id]").get_attribute("data-screen-id")
            h1_text = (await page.locator("h1").inner_text()).strip()
            body_text = (await page.locator("main").inner_text()).strip()

            assert screen_id == route_id, f"Expected screen {route_id}, got {screen_id}"
            assert expected_title in h1_text, f"Expected title '{expected_title}', got '{h1_text}'"
            assert len(body_text) > 50, f"Blank screen detected on {href}"
            visited.append({"route_id": route_id, "href": href, "h1": h1_text})

        # Explicitly verify header Settings button does NOT open Security screen
        await page.locator('a[aria-label="Open System Settings"]').click()
        await page.wait_for_url(f"{base_url}/settings")
        await page.wait_for_selector('[data-screen-id="settings"]')
        assert "Ecosystem Preferences & Settings" in (await page.locator("h1").inner_text())

        # Verify Theme Toggle switches dark <-> light cleanly
        before_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
        await page.locator('button[aria-label^="Switch to "]').click()
        after_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
        assert before_dark != after_dark, "Theme toggle failed to switch class"

        await browser.close()

    assert not console_errors, f"Browser console errors: {console_errors}"
    assert not page_errors, f"Uncaught page errors: {page_errors}"
    return {"status": "UI_NAVIGATION_OK", "routes_verified": len(visited), "theme_toggled": True}


def main() -> int:
    port = _free_port()
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    proc = subprocess.Popen(
        [npm_cmd, "run", "start", "--", "-p", str(port)],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_port(port)
        result = asyncio.run(run_nav_checks(f"http://127.0.0.1:{port}"))
        print(json.dumps(result, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
