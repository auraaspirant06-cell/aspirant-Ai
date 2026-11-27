"""Commercial-grade SVG, transparent PNG, ICO, favicon, social kit & brand kit generator.

Renders precision vector SVGs via headless Microsoft Edge (Playwright) for true
anti-aliased gradients, glow filters, and alpha transparency, then packages multi-size
ICO/favicon icons with Pillow.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "docs" / "brand"
ASSETS_DIR = BRAND_DIR / "assets"
SOCIAL_DIR = BRAND_DIR / "social-kit"
SPLASH_DIR = BRAND_DIR / "splash-screens"

PALETTE = {
    "brand": "ASPIRANT AI",
    "tagline": "Intelligence Beyond Assistance",
    "products": ["NOVA", "MJ", "MAX"],
    "colors": {
        "deep_black": "#05070E",
        "obsidian_surface": "#0B1021",
        "electric_blue": "#0EA5E9",
        "royal_blue": "#3B82F6",
        "neon_purple": "#8B5CF6",
        "deep_purple": "#6D28D9",
        "white_accent": "#F8FAFC",
        "muted_slate": "#94A3B8",
    },
}

MAIN_MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070B18"/>
      <stop offset="100%" stop-color="#0F172A"/>
    </linearGradient>
    <linearGradient id="primaryGrad" x1="10%" y1="90%" x2="90%" y2="10%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="50%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#8B5CF6"/>
    </linearGradient>
    <linearGradient id="coreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="55%" stop-color="#BAE6FD"/>
      <stop offset="100%" stop-color="#DDD6FE"/>
    </linearGradient>
    <filter id="glow" x="-25%" y="-25%" width="150%" height="150%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  {backdrop}
  <circle cx="256" cy="256" r="196" fill="none" stroke="url(#primaryGrad)" stroke-width="6" stroke-dasharray="280 44 120 44" opacity="0.88"/>
  <circle cx="256" cy="256" r="172" fill="none" stroke="#FFFFFF" stroke-opacity="0.16" stroke-width="2"/>
  <g filter="url(#glow)">
    <path d="M256 76 L396 392 L342 392 L256 196 L170 392 L116 392 Z" fill="url(#primaryGrad)"/>
    <path d="M188 312 L256 268 L324 312 L298 344 L256 318 L214 344 Z" fill="url(#coreGrad)"/>
  </g>
  <polygon points="256,124 270,152 298,166 270,180 256,208 242,180 214,166 242,152" fill="#FFFFFF"/>
  <circle cx="96" cy="144" r="9" fill="#0EA5E9"/>
  <circle cx="416" cy="368" r="9" fill="#8B5CF6"/>
  <circle cx="404" cy="126" r="6" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

PRODUCT_MARK_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="pg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect x="12" y="12" width="232" height="232" rx="56" fill="#070B18" stroke="url(#pg)" stroke-width="6"/>
  <circle cx="128" cy="128" r="78" fill="none" stroke="url(#pg)" stroke-width="4" opacity="0.45"/>
  {glyph}
</svg>"""

FULL_LOCKUP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320">
  <defs>
    <linearGradient id="txtGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="65%" stop-color="#BAE6FD"/>
      <stop offset="100%" stop-color="#C4B5FD"/>
    </linearGradient>
    <linearGradient id="markGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="100%" stop-color="#8B5CF6"/>
    </linearGradient>
  </defs>
  {bg}
  <g transform="translate(54,32) scale(0.5)">
    <circle cx="256" cy="256" r="196" fill="none" stroke="url(#markGrad)" stroke-width="10" stroke-dasharray="280 44 120 44"/>
    <path d="M256 76 L396 392 L342 392 L256 196 L170 392 L116 392 Z" fill="url(#markGrad)"/>
    <path d="M188 312 L256 268 L324 312 L298 344 L256 318 L214 344 Z" fill="#FFFFFF"/>
    <polygon points="256,124 270,152 298,166 270,180 256,208 242,180 214,166 242,152" fill="#FFFFFF"/>
  </g>
  <text x="355" y="158" fill="url(#txtGrad)" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="86" font-weight="800" letter-spacing="8">ASPIRANT AI</text>
  <text x="360" y="218" fill="#94A3B8" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="28" font-weight="600" letter-spacing="6">INTELLIGENCE BEYOND ASSISTANCE</text>
  <rect x="360" y="242" width="110" height="28" rx="14" fill="#0EA5E9" fill-opacity="0.18" stroke="#0EA5E9"/>
  <text x="415" y="261" text-anchor="middle" fill="#BAE6FD" font-family="Segoe UI, sans-serif" font-size="15" font-weight="700" letter-spacing="2">NOVA</text>
  <rect x="486" y="242" width="90" height="28" rx="14" fill="#8B5CF6" fill-opacity="0.22" stroke="#8B5CF6"/>
  <text x="531" y="261" text-anchor="middle" fill="#DDD6FE" font-family="Segoe UI, sans-serif" font-size="15" font-weight="700" letter-spacing="2">MJ</text>
  <rect x="592" y="242" width="98" height="28" rx="14" fill="#3B82F6" fill-opacity="0.20" stroke="#3B82F6"/>
  <text x="641" y="261" text-anchor="middle" fill="#DBEAFE" font-family="Segoe UI, sans-serif" font-size="15" font-weight="700" letter-spacing="2">MAX</text>
</svg>"""


def _social_svg(width: int, height: int, subtitle: str) -> str:
    cx = int(width * 0.19)
    cy = int(height * 0.5)
    scale = min(width, height) / 920.0
    title_size = max(44, int(width * 0.056))
    sub_size = max(20, int(width * 0.021))
    tx = int(width * 0.34)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <radialGradient id="orb1" cx="18%" cy="22%" r="55%">
      <stop offset="0%" stop-color="#0EA5E9" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="#05070E" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="orb2" cx="85%" cy="80%" r="55%">
      <stop offset="0%" stop-color="#8B5CF6" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="#05070E" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="gBrand" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="100%" stop-color="#8B5CF6"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="#05070E"/>
  <rect width="{width}" height="{height}" fill="url(#orb1)"/>
  <rect width="{width}" height="{height}" fill="url(#orb2)"/>
  <g opacity="0.12" stroke="#3B82F6" stroke-width="1">
    <line x1="0" y1="{int(height*0.25)}" x2="{width}" y2="{int(height*0.25)}"/>
    <line x1="0" y1="{int(height*0.75)}" x2="{width}" y2="{int(height*0.75)}"/>
  </g>
  <g transform="translate({cx - int(256*scale)}, {cy - int(256*scale)}) scale({scale:.3f})">
    <circle cx="256" cy="256" r="196" fill="none" stroke="url(#gBrand)" stroke-width="10" stroke-dasharray="280 44 120 44"/>
    <path d="M256 76 L396 392 L342 392 L256 196 L170 392 L116 392 Z" fill="url(#gBrand)"/>
    <path d="M188 312 L256 268 L324 312 L298 344 L256 318 L214 344 Z" fill="#FFFFFF"/>
    <polygon points="256,124 270,152 298,166 270,180 256,208 242,180 214,166 242,152" fill="#FFFFFF"/>
  </g>
  <text x="{tx}" y="{int(height*0.46)}" fill="#FFFFFF" font-family="Segoe UI, Inter, sans-serif" font-size="{title_size}" font-weight="800" letter-spacing="6">ASPIRANT AI</text>
  <text x="{tx}" y="{int(height*0.58)}" fill="#BAE6FD" font-family="Segoe UI, Inter, sans-serif" font-size="{sub_size}" font-weight="600" letter-spacing="4">{subtitle}</text>
  <text x="{tx}" y="{int(height*0.69)}" fill="#94A3B8" font-family="Segoe UI, Inter, sans-serif" font-size="{max(16, int(sub_size*0.78))}" font-weight="600" letter-spacing="3">NOVA DESKTOP  •  MJ INTELLIGENCE  •  MAX MOBILE</text>
</svg>"""


def _splash_svg(width: int, height: int, mode_label: str) -> str:
    is_portrait = height > width
    cx = width // 2
    cy = int(height * (0.42 if is_portrait else 0.44))
    scale = (min(width, height) * 0.28) / 512.0
    title_y = int(cy + 260 * scale + 70)
    sub_y = title_y + (48 if is_portrait else 54)
    title_size = 54 if is_portrait else 64
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <radialGradient id="spGlow" cx="50%" cy="42%" r="60%">
      <stop offset="0%" stop-color="#0EA5E9" stop-opacity="0.28"/>
      <stop offset="55%" stop-color="#8B5CF6" stop-opacity="0.14"/>
      <stop offset="100%" stop-color="#05070E" stop-opacity="1"/>
    </radialGradient>
    <linearGradient id="spBrand" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="55%" stop-color="#BAE6FD"/>
      <stop offset="100%" stop-color="#C4B5FD"/>
    </linearGradient>
    <linearGradient id="spA" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="50%" stop-color="#3B82F6"/>
      <stop offset="100%" stop-color="#8B5CF6"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="#05070E"/>
  <rect width="{width}" height="{height}" fill="url(#spGlow)"/>
  <g transform="translate({cx - 256*scale},{cy - 256*scale}) scale({scale})">
    <circle cx="256" cy="256" r="210" fill="none" stroke="url(#spA)" stroke-width="8" stroke-dasharray="300 44 120 44"/>
    <path d="M256 76 L396 392 L342 392 L256 196 L170 392 L116 392 Z" fill="url(#spA)"/>
    <path d="M188 312 L256 268 L324 312 L298 344 L256 318 L214 344 Z" fill="#FFFFFF"/>
    <polygon points="256,124 270,152 298,166 270,180 256,208 242,180 214,166 242,152" fill="#FFFFFF"/>
  </g>
  <text x="{cx}" y="{title_y}" text-anchor="middle" fill="url(#spBrand)" font-family="Segoe UI, Inter, sans-serif" font-size="{title_size}" font-weight="800" letter-spacing="8">ASPIRANT AI</text>
  <text x="{cx}" y="{sub_y}" text-anchor="middle" fill="#94A3B8" font-family="Segoe UI, Inter, sans-serif" font-size="22" font-weight="600" letter-spacing="5">{mode_label} • INTELLIGENCE BEYOND ASSISTANCE</text>
</svg>"""


async def _render_svgs(jobs: list[tuple[Path, Path, int, int, bool]]) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page()
        for svg_path, png_path, width, height, transparent in jobs:
            await page.set_viewport_size({"width": width, "height": height})
            svg_markup = svg_path.read_text(encoding="utf-8")
            html = (
                "<!doctype html><html><body style='margin:0;padding:0;overflow:hidden;background:transparent;'>"
                f"{svg_markup}</body></html>"
            )
            await page.set_content(html)
            await page.screenshot(path=str(png_path), omit_background=transparent)
        await browser.close()


def main() -> None:
    for d in (BRAND_DIR, ASSETS_DIR, SOCIAL_DIR, SPLASH_DIR):
        d.mkdir(parents=True, exist_ok=True)

    (ASSETS_DIR / "aspirant-mark.svg").write_text(
        MAIN_MARK_SVG.format(backdrop='<rect x="16" y="16" width="480" height="480" rx="112" fill="url(#bgGrad)"/>'),
        encoding="utf-8",
    )
    (ASSETS_DIR / "aspirant-mark-transparent.svg").write_text(
        MAIN_MARK_SVG.format(backdrop=""),
        encoding="utf-8",
    )
    (ASSETS_DIR / "aspirant-logo-dark.svg").write_text(
        FULL_LOCKUP_SVG.format(bg='<rect width="1200" height="320" rx="28" fill="#05070E"/>'),
        encoding="utf-8",
    )
    (ASSETS_DIR / "aspirant-logo-transparent.svg").write_text(
        FULL_LOCKUP_SVG.format(bg=""),
        encoding="utf-8",
    )

    (ASSETS_DIR / "nova-mark.svg").write_text(
        PRODUCT_MARK_TEMPLATE.format(
            c1="#0EA5E9",
            c2="#38BDF8",
            glyph='<path d="M84 178 V78 L172 178 V78" fill="none" stroke="url(#pg)" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/><circle cx="172" cy="78" r="10" fill="#FFFFFF"/>',
        ),
        encoding="utf-8",
    )
    (ASSETS_DIR / "mj-mark.svg").write_text(
        PRODUCT_MARK_TEMPLATE.format(
            c1="#8B5CF6",
            c2="#EC4899",
            glyph='<path d="M68 176 V84 L112 138 L156 84 V176" fill="none" stroke="url(#pg)" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/><circle cx="188" cy="94" r="12" fill="#FFFFFF"/><path d="M188 122 V158 C188 174 172 182 158 176" fill="none" stroke="#C4B5FD" stroke-width="14" stroke-linecap="round"/>',
        ),
        encoding="utf-8",
    )
    (ASSETS_DIR / "max-mark.svg").write_text(
        PRODUCT_MARK_TEMPLATE.format(
            c1="#3B82F6",
            c2="#8B5CF6",
            glyph='<polygon points="128,56 186,128 128,200 70,128" fill="none" stroke="url(#pg)" stroke-width="16"/><circle cx="128" cy="128" r="22" fill="#FFFFFF"/>',
        ),
        encoding="utf-8",
    )

    social_specs = [
        ("og-banner-1200x630", 1200, 630, "INTELLIGENCE BEYOND ASSISTANCE"),
        ("x-header-1500x500", 1500, 500, "UNIFIED AI OPERATING ECOSYSTEM"),
        ("linkedin-banner-1584x396", 1584, 396, "ENTERPRISE PERSONAL AI PLATFORM"),
        ("social-square-1080x1080", 1080, 1080, "INTELLIGENCE BEYOND ASSISTANCE"),
        ("youtube-banner-2560x1440", 2560, 1440, "INTELLIGENCE BEYOND ASSISTANCE"),
    ]
    jobs: list[tuple[Path, Path, int, int, bool]] = [
        (ASSETS_DIR / "aspirant-mark.svg", ASSETS_DIR / "app-icon-512.png", 512, 512, True),
        (ASSETS_DIR / "aspirant-mark-transparent.svg", ASSETS_DIR / "aspirant-mark-transparent.png", 512, 512, True),
        (ASSETS_DIR / "aspirant-logo-dark.svg", ASSETS_DIR / "aspirant-logo-dark.png", 1200, 320, False),
        (ASSETS_DIR / "aspirant-logo-transparent.svg", ASSETS_DIR / "aspirant-logo-transparent.png", 1200, 320, True),
        (ASSETS_DIR / "nova-mark.svg", ASSETS_DIR / "nova-mark.png", 256, 256, True),
        (ASSETS_DIR / "mj-mark.svg", ASSETS_DIR / "mj-mark.png", 256, 256, True),
        (ASSETS_DIR / "max-mark.svg", ASSETS_DIR / "max-mark.png", 256, 256, True),
    ]
    for name, w, h, sub in social_specs:
        svg_p = SOCIAL_DIR / f"{name}.svg"
        svg_p.write_text(_social_svg(w, h, sub), encoding="utf-8")
        jobs.append((svg_p, SOCIAL_DIR / f"{name}.png", w, h, False))

    splash_specs = [
        ("splash-desktop-1920x1080", 1920, 1080, "NOVA WORKSTATION"),
        ("splash-mobile-1080x1920", 1080, 1920, "MAX MOBILE COMPANION"),
    ]
    for name, w, h, label in splash_specs:
        svg_p = SPLASH_DIR / f"{name}.svg"
        svg_p.write_text(_splash_svg(w, h, label), encoding="utf-8")
        jobs.append((svg_p, SPLASH_DIR / f"{name}.png", w, h, False))

    asyncio.run(_render_svgs(jobs))

    master_icon = Image.open(ASSETS_DIR / "app-icon-512.png").convert("RGBA")
    master_icon.resize((1024, 1024), Image.Resampling.LANCZOS).save(ASSETS_DIR / "app-icon-1024.png")
    master_icon.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS_DIR / "app-icon-256.png")
    master_icon.resize((192, 192), Image.Resampling.LANCZOS).save(ASSETS_DIR / "android-chrome-192x192.png")
    master_icon.resize((180, 180), Image.Resampling.LANCZOS).save(ASSETS_DIR / "apple-touch-icon.png")
    master_icon.resize((32, 32), Image.Resampling.LANCZOS).save(ASSETS_DIR / "favicon-32x32.png")
    master_icon.save(
        ASSETS_DIR / "app-icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    master_icon.save(
        ASSETS_DIR / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )

    for target_dir in (
        ROOT / "frontend" / "public",
        ROOT / "frontend" / "public" / "brand",
        ROOT / "desktop" / "assets",
        ROOT / "mobile" / "assets" / "brand",
    ):
        target_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ASSETS_DIR / "favicon.ico", ROOT / "frontend" / "public" / "favicon.ico")
    shutil.copy2(ASSETS_DIR / "aspirant-mark-transparent.svg", ROOT / "frontend" / "public" / "favicon.svg")
    shutil.copy2(ASSETS_DIR / "apple-touch-icon.png", ROOT / "frontend" / "public" / "apple-touch-icon.png")
    shutil.copy2(ASSETS_DIR / "aspirant-logo-transparent.png", ROOT / "frontend" / "public" / "brand" / "logo-transparent.png")
    shutil.copy2(ASSETS_DIR / "aspirant-mark-transparent.png", ROOT / "frontend" / "public" / "brand" / "mark-transparent.png")
    shutil.copy2(ASSETS_DIR / "nova-mark.png", ROOT / "frontend" / "public" / "brand" / "nova-mark.png")
    shutil.copy2(ASSETS_DIR / "mj-mark.png", ROOT / "frontend" / "public" / "brand" / "mj-mark.png")
    shutil.copy2(ASSETS_DIR / "max-mark.png", ROOT / "frontend" / "public" / "brand" / "max-mark.png")
    shutil.copy2(ASSETS_DIR / "app-icon.ico", ROOT / "desktop" / "assets" / "app-icon.ico")
    shutil.copy2(ASSETS_DIR / "app-icon-512.png", ROOT / "desktop" / "assets" / "app-icon.png")
    shutil.copy2(SPLASH_DIR / "splash-desktop-1920x1080.png", ROOT / "desktop" / "assets" / "splash-desktop.png")
    shutil.copy2(ASSETS_DIR / "app-icon-512.png", ROOT / "mobile" / "assets" / "brand" / "app-icon.png")
    shutil.copy2(ASSETS_DIR / "max-mark.png", ROOT / "mobile" / "assets" / "brand" / "max-mark.png")
    shutil.copy2(SPLASH_DIR / "splash-mobile-1080x1920.png", ROOT / "mobile" / "assets" / "brand" / "splash-mobile.png")

    loader_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
  <defs>
    <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="100%" stop-color="#8B5CF6"/>
    </linearGradient>
  </defs>
  <rect width="120" height="120" rx="28" fill="#05070E"/>
  <circle cx="60" cy="60" r="42" fill="none" stroke="url(#lg)" stroke-width="5" stroke-dasharray="180 84" stroke-linecap="round">
    <animateTransform attributeName="transform" type="rotate" from="0 60 60" to="360 60 60" dur="1.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="60" cy="60" r="28" fill="none" stroke="#38BDF8" stroke-width="3" stroke-dasharray="72 52">
    <animateTransform attributeName="transform" type="rotate" from="360 60 60" to="0 60 60" dur="2.1s" repeatCount="indefinite"/>
  </circle>
  <path d="M60 36 L78 80 L69 80 L60 56 L51 80 L42 80 Z" fill="url(#lg)"/>
</svg>"""
    (ASSETS_DIR / "aspirant-loader.svg").write_text(loader_svg, encoding="utf-8")
    shutil.copy2(ASSETS_DIR / "aspirant-loader.svg", ROOT / "frontend" / "public" / "brand" / "loader.svg")
    shutil.copy2(ASSETS_DIR / "aspirant-loader.svg", ROOT / "desktop" / "assets" / "loader.svg")

    (BRAND_DIR / "brand-tokens.json").write_text(json.dumps(PALETTE, indent=2), encoding="utf-8")
    (BRAND_DIR / "brand-kit.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>ASPIRANT AI Brand Kit</title>
<style>body{{background:#05070E;color:#F8FAFC;font-family:Segoe UI,sans-serif;padding:40px;max-width:1100px;margin:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}}
.card{{background:#0B1021;border:1px solid rgba(139,92,246,.3);border-radius:16px;padding:20px}}
img{{max-width:100%;height:auto}}</style></head>
<body><h1>ASPIRANT AI — Brand Kit</h1><p>{PALETTE['tagline']}</p>
<div class="card"><img src="assets/aspirant-logo-dark.png" alt="Main Logo"></div>
<h2>Product Marks</h2><div class="grid">
<div class="card"><h3>NOVA</h3><img src="assets/nova-mark.png" width="128"></div>
<div class="card"><h3>MJ</h3><img src="assets/mj-mark.png" width="128"></div>
<div class="card"><h3>MAX</h3><img src="assets/max-mark.png" width="128"></div></div>
<h2>Social Media Kit</h2><div class="grid">
<div class="card"><h4>OG Banner (1200x630)</h4><img src="social-kit/og-banner-1200x630.png"></div>
<div class="card"><h4>Square (1080x1080)</h4><img src="social-kit/social-square-1080x1080.png"></div></div></body></html>""",
        encoding="utf-8",
    )
    print(f"Generated {len(jobs)} rendered PNGs + ICOs + brand kit in {BRAND_DIR}")


if __name__ == "__main__":
    main()
