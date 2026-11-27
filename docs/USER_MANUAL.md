# User Manual — NOVA, MJ, MAX & Web Console

## 1. NOVA — Desktop AI Assistant (Windows)
- **Wake Words:** Say `"Hey Nova"`, `"Hey Aspirant"`, or press global hotkey `Ctrl+Shift+N` in the Electron/Tauri shell (or click Push-to-Talk in the native PySide6 Voice view).
- **Clipboard Intelligence:** Copy any URL, stack trace, Python/TS snippet, JSON payload, or email address; NOVA classifies it automatically and proposes one-click actions (`/api/v1/nova/clipboard/analyze`).
- **Command & File Guardrails:** All OS/terminal commands run through `command_policy.inspect_command`. Destructive commands (`rm -rf`, registry deletes, `format`) are blocked or gated behind explicit approval.
- **Native Workstation (`src/aspirant/`):** Provides Coding Studio, File Manager with reversible `data/trash/`, 19 `.gov.in` helper workflows, Image Studio, Video Studio, and Emergency Stop (`Ctrl+Alt+Shift+E`).

## 2. MJ — Human-Like Intelligent Companion
- **Persistent Context:** Every conversation turn, preference, and knowledge chunk persists encrypted in the database and indexed in Qdrant/Chroma so MJ remembers across sessions and devices.
- **Document Understanding:** Upload or paste notes/specs into `/mj/document/understand` to index chunks into RAG and extract executive action items.
- **Email & Calendar:** Use `/mj/email/assist` for context-aware replies and `/mj/calendar/analyze` to spot overlapping events and book deep-focus blocks.
- **Deep Research & Planning:** Invoke `/mj/research/plan` to trigger the Research + Planning + Content + Productivity agents and automatically track the resulting Goal & milestones.

## 3. MAX — Android-First Mobile Companion
- **Offline First:** Voice memos, quick notes, and habit check-ins persist immediately into on-device SQLite (`MaxLocalDatabase`) even without network connectivity.
- **Delta Sync:** Tap Sync (top-right icon in the app bar) to push offline notes and habit check-ins to `/api/v1/max/sync` and receive updated goals, reminders, and AI summaries from NOVA/MJ.
- **Security:** Access & refresh JWT tokens are stored encrypted in Android Keystore via `flutter_secure_storage`.

## 4. Next.js Web Control Center (`http://127.0.0.1:3000`)
- Use the **Connect JWT** button in the top bar to register or sign in against the FastAPI server (or explore interactive preview flows when offline).
- Switch themes cleanly between **Deep Space Dark** and **Clean Daylight** via the bottom-left toggle.
- Inspect live multi-agent traces (`RESEARCH`, `AUTOMATION`, `CODING`, `CONTENT`, `PRODUCTIVITY`, `PLANNING`, `SUPPORT`) and query semantic memory interactively.
