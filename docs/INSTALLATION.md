# Installation Guide — Aspirant AI Ecosystem

## Prerequisites
- **Python 3.12+** with [`uv`](https://docs.astral.sh/uv/) (tested locally on Python `3.14.10` + `uv 0.13.7`)
- **Node.js 20+** and `npm` (for `/frontend` Next.js web app and `/desktop/electron` syntax/run)
- **Optional External SDKs** (required only if building native containers/installers locally):
  - Docker Desktop / Docker Engine (full multi-service stack: PostgreSQL, Redis, Qdrant, Chroma, Celery)
  - Flutter SDK 3.24+ & Android SDK (to build Android APK/AAB from `/mobile`)
  - Rust + Cargo (`cargo-tauri`) (to compile the `/desktop/src-tauri` native shell)

## 1. Environment Configuration
Never overwrite `.env` if you already customized secrets:
```powershell
cd C:\Users\harsh\Documents\AspirantAI
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```
Optional keys to set in `.env`:
- `GEMINI_API_KEY` — Primary Gemini 4 / Gemini 3.8 Live / Nano Banana / Omni 1.2 access
- `OPENAI_API_KEY` & `OPENAI_BASE_URL` — GPT-compatible provider routing
- `DATABASE_URL` — Defaults locally to SQLite (`data/aspirant_ecosystem.db`), set to `postgresql+psycopg://...` for PostgreSQL
- `ASPIRANT_JWT_SECRET` & `ASPIRANT_ENCRYPTION_KEY` — Fixed secrets across backend restarts

## 2. Backend & Native Desktop Python Setup
```powershell
cd C:\Users\harsh\Documents\AspirantAI
uv sync
```
Run initial database migrations:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_migrations.ps1
```
Start the Ecosystem FastAPI backend (`http://127.0.0.1:8000`):
```powershell
$env:PYTHONPATH = "C:\Users\harsh\Documents\AspirantAI"
uv run python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Or launch the native Windows PySide6 NOVA Workstation (`13` views):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch_aspirant.ps1
```

## 3. Frontend Web Console (`/frontend`)
```powershell
cd C:\Users\harsh\Documents\AspirantAI\frontend
npm install
npm run dev
```
Open `http://127.0.0.1:3000`.

## 4. Desktop Shell (`/desktop`)
Electron mode:
```powershell
cd C:\Users\harsh\Documents\AspirantAI\desktop\electron
npm install
npm start
```
Tauri mode (requires Rust toolchain):
```powershell
cd C:\Users\harsh\Documents\AspirantAI\desktop\src-tauri
cargo tauri dev
```

## 5. Android Mobile App (`/mobile` — MAX)
Requires Flutter SDK + Android SDK:
```bash
cd mobile
flutter pub get
flutter run --dart-define=ASPIRANT_API_URL=http://10.0.2.2:8000/api/v1
```

## 6. One-Click Operational Scripts (`scripts/`)
- Full setup (Python + Alembic + Frontend):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```
- Launch Desktop / Web / Ecosystem (optional `-RegisterStartup` / `-UnregisterStartup` Windows Startup shortcut toggle):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Mode desktop
```
- Health Check & Clean Stop:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\health-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\update.ps1
```
