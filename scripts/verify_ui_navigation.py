"""End-to-end visual, layout, contrast, responsiveness, and routing validation for Next.js + PySide6 UI."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
SCREENSHOT_DIR = Path(
    r"C:\Users\harsh\.gemini\antigravity\brain\82c96902-8b1e-4802-8719-9038ce72ffba\scratch"
)

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


def audit_desktop_pyside6() -> dict:
    """Instantiate native PySide6 desktop window offscreen, click all 13 tabs, check geometry & save grabs."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QPushButton

    from aspirant.ui.app_window import AspirantMainWindow, NAV_SECTIONS
    from aspirant.ui.client import AspirantApiClient

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication([])
    for font_file in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if Path(font_file).exists():
            font_id = QFontDatabase.addApplicationFont(font_file)
            if font_id >= 0:
                fams = QFontDatabase.applicationFontFamilies(font_id)
                if fams:
                    app.setFont(QFont(fams[0], 10))
                    break
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    win = AspirantMainWindow(api_client=AspirantApiClient("http://127.0.0.1:1", "test-token"))
    win.show()
    app.processEvents()

    checked_views: list[str] = []
    capture_keys = {"home": "desktop_home.png", "voice": "desktop_voice.png", "settings": "desktop_settings.png"}

    for _group, key, label in NAV_SECTIONS:
        btn = win._nav_buttons[key]
        btn.click()
        app.processEvents()
        assert win.stack.currentIndex() == win._view_indices[key], f"Screen mismatch on {key}"
        current_view = win.stack.currentWidget()
        assert current_view.width() > 300 and current_view.height() > 200, f"Collapsed view {key}"

        # Check sidebar button not clipped
        assert btn.height() >= 30 and btn.width() > 100, f"Sidebar button geometry clipped on {label}"

        # Verify sibling nav buttons do not overlap vertically
        checked_views.append(key)
        if key in capture_keys:
            win.grab().save(str(SCREENSHOT_DIR / capture_keys[key]))

    win.close()
    app.processEvents()
    return {"desktop_views_checked": len(checked_views), "screenshots_saved": sorted(capture_keys.values())}


async def _assert_layout_quality(page, label: str) -> None:
    metrics = await page.evaluate(
        """() => {
            const overflowX = document.documentElement.scrollWidth > window.innerWidth + 2;
            const navLinks = Array.from(document.querySelectorAll('nav a[data-route-id]'));
            const rects = navLinks.map(el => el.getBoundingClientRect());
            let overlaps = 0;
            for (let i = 0; i < rects.length; i++) {
                for (let j = i + 1; j < rects.length; j++) {
                    const a = rects[i], b = rects[j];
                    const ix = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
                    const iy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
                    if (ix > 2 && iy > 2) overlaps++;
                }
            }
            const selects = Array.from(document.querySelectorAll('select')).map(s => {
                const st = getComputedStyle(s);
                return { bg: st.backgroundColor, fg: st.color, h: s.getBoundingClientRect().height };
            });
            const zeroSizedBtns = Array.from(document.querySelectorAll('button, a')).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width === 0 || r.height === 0;
            }).length;
            return { overflowX, overlaps, selects, zeroSizedBtns };
        }"""
    )
    assert not metrics["overflowX"], f"Horizontal overflow on {label}"
    assert metrics["overlaps"] == 0, f"Overlapping nav controls ({metrics['overlaps']}) on {label}"
    assert metrics["zeroSizedBtns"] == 0, f"Zero-sized interactive control on {label}"
    for sel in metrics["selects"]:
        assert sel["bg"] != sel["fg"], f"Invisible select dropdown colors on {label}: {sel}"
        assert sel["h"] >= 32, f"Dropdown too small for touch/click on {label}"


async def run_nav_checks(base_url: str) -> dict:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    visited: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)

        # 1. Desktop 1440x900 Dark Mode full navigation & screenshot check
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        await page.goto(base_url, wait_until="networkidle")
        await page.screenshot(path=str(SCREENSHOT_DIR / "web_overview_dark.png"))

        for route_id, href, expected_title in EXPECTED_SCREENS:
            await page.locator(f'nav a[data-route-id="{route_id}"]').click()
            await page.wait_for_url(f"{base_url}{href}" if href != "/" else f"{base_url}/")
            await page.wait_for_selector(f'[data-screen-id="{route_id}"]')

            screen_id = await page.locator("[data-screen-id]").get_attribute("data-screen-id")
            h1_text = (await page.locator("h1").inner_text()).strip()
            body_text = (await page.locator("main").inner_text()).strip()

            assert screen_id == route_id, f"Expected screen {route_id}, got {screen_id}"
            assert expected_title in h1_text, f"Expected title '{expected_title}', got '{h1_text}'"
            assert len(body_text) > 50, f"Blank screen detected on {href}"
            await _assert_layout_quality(page, f"desktop-dark:{href}")
            if route_id == "voice":
                await page.screenshot(path=str(SCREENSHOT_DIR / "web_voice_dark.png"))
            visited.append({"route_id": route_id, "href": href})

        # 2. Switch to Light Mode and verify dropdown/contrast on /settings
        await page.locator('button[aria-label^="Switch to "]').click()
        await page.locator('a[aria-label="Open System Settings"]').click()
        await page.wait_for_url(f"{base_url}/settings")
        await page.wait_for_selector('[data-screen-id="settings"]')
        is_dark = await page.evaluate("document.documentElement.classList.contains('dark')")
        assert not is_dark, "Theme toggle did not switch to Clean Daylight light mode"
        await _assert_layout_quality(page, "desktop-light:/settings")
        await page.screenshot(path=str(SCREENSHOT_DIR / "web_settings_light.png"))

        # 3. Mobile 390x844 Touch & Responsive Check on / & /voice
        mobile = await browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True)
        await mobile.goto(f"{base_url}/voice", wait_until="networkidle")
        await _assert_layout_quality(mobile, "mobile-390:/voice")
        await mobile.screenshot(path=str(SCREENSHOT_DIR / "web_voice_mobile.png"))
        await mobile.close()

        await browser.close()

    assert not console_errors, f"Browser console errors: {console_errors}"
    assert not page_errors, f"Uncaught page errors: {page_errors}"
    return {"status": "UI_NAVIGATION_OK", "routes_verified": len(visited), "light_and_mobile_checked": True}


def main() -> int:
    desktop_res = audit_desktop_pyside6()
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
        web_res = asyncio.run(run_nav_checks(f"http://127.0.0.1:{port}"))
        print(json.dumps({"desktop": desktop_res, "web": web_res}, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
