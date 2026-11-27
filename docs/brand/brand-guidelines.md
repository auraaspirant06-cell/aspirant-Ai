# Aspirant AI — Brand Identity Guidelines

**Tagline:** *Intelligence Beyond Assistance*

## 1. Brand Architecture
Aspirant AI is a unified autonomous intelligence ecosystem spanning three specialized products:

- **NOVA** — Advanced Desktop AI Assistant for Windows (System & browser automation, wake word `"Hey Nova"`, screen vision/OCR, multi-agent dispatch).
- **MJ** — Human-Like Intelligent Companion (Persistent memory, context awareness, user profiling, goal tracking, deep research, multi-step reasoning).
- **MAX** — Mobile AI Companion (Android-first Flutter client, offline-ready, voice commands, smart reminders, habit tracking, AI notes, real-time cross-device sync).

## 2. Visual Identity & Color System

| Token | Hex | Usage |
| --- | --- | --- |
| Primary Electric Blue | `#0EA5E9` / `#3B82F6` | Primary CTAs, active orbital strokes, NOVA accents |
| Secondary Neon Purple | `#8B5CF6` / `#6366F1` | Gradients, MJ intelligence accents, agent reasoning glow |
| Background Deep Black | `#05070E` / `#0B1020` | Primary dark surfaces, desktop chrome, app icon backdrop |
| Elevated Dark Surface | `#111827` | Cards, panels, frosted glass containers |
| Light Mode Surface | `#F8FAFC` / `#FFFFFF` | Light theme canvas & cards |
| Primary Ink (Dark) | `#F8FAFC` | Headings and high-emphasis UI copy |
| Muted Ink | `#94A3B8` | Secondary labels, telemetry, metadata |
| Success Emerald | `#10B981` | Health checks, synced status, verified runs |
| Warning Amber | `#F59E0B` | Rate-limit alerts, pending confirmations |
| Danger Crimson | `#EF4444` | Security blocks, emergency stop |

## 3. Logo & Mark Usage
All master assets are generated from vector SVG templates via `scripts/generate_brand_assets.py` into `docs/brand/`:

- **Master Lockups:** `assets/aspirant-logo-dark.svg` / `.png`, `assets/aspirant-logo-light.svg` / `.png`
- **Standalone Mark & Transparent Overlay:** `assets/aspirant-mark-transparent.svg` / `.png`
- **Desktop & App Icons:** `assets/app-icon-512.png`, `assets/app-icon.ico`, `assets/favicon-64.png`, `assets/favicon.ico`
- **Product Sub-Marks:** `assets/nova-mark.png`, `assets/mj-mark.png`, `assets/max-mark.png`
- **Social Media Kit:**
  - OpenGraph / GitHub Preview: `social-kit/og-banner-1200x630.png`
  - Twitter / X Header: `social-kit/twitter-header-1500x500.png`
  - LinkedIn Cover: `social-kit/linkedin-cover-1584x396.png`
  - Square Social Avatar: `social-kit/avatar-1080x1080.png`
  - YouTube / Hero Backdrop: `social-kit/youtube-banner-2560x1440.png`

## 4. Clear Space & Contrast Rules
- Maintain at least `0.25x` mark width clear space around the Aspirant "A" orbital emblem.
- Always pair `aspirant-logo-dark.*` with dark backgrounds (`#05070E`–`#111827`) and `aspirant-logo-light.*` with light surfaces (`#F8FAFC`–`#FFFFFF`).
- Never distort aspect ratios, add drop shadows that muddy the orbital ring, or alter the Electric Blue -> Neon Purple gradient direction.

## 5. Typography
- **UI & Display:** `Inter` / `Segoe UI Variable` / system sans-serif with tight display tracking (`-0.02em`) for headings.
- **Wordmark Tracking:** Wide geometric uppercase (`letter-spacing: 6px–12px`) for `ASPIRANT AI` and sub-product pills (`NOVA`, `MJ`, `MAX`).
- **Code & Telemetry:** `JetBrains Mono` / `Cascadia Code` / monospace.
