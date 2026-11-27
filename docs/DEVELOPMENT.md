# Development Guide — Contributing & Extending Aspirant AI

## Coding Standards
- **Backend (`backend/`, `apps/`):** Maintain strict separation between `domain/` (pure dataclasses + `Protocol` interfaces), `infrastructure/` (SQLAlchemy ORM + Redis + Vector stores), `services/` (use-case orchestration), and `api/v1/` (thin HTTP transport handlers).
- **Windows Smart App Control Note:** On Windows environments with Strict Application Control, keep SQLAlchemy pinned to `<2.1` (`sqlalchemy>=2.0.36,<2.1`) and run Python scripts via `uv run python -m ...` rather than raw `.venv\Scripts\*.exe` shims.
- **Database Migrations:** After editing `backend/app/infrastructure/db/models.py`, generate and review an Alembic migration:
  ```powershell
  cd C:\Users\harsh\Documents\AspirantAI\backend
  $env:PYTHONPATH = ".."
  uv run --directory .. python -m alembic revision --autogenerate -m "describe_change"
  ```

## Regenerating Brand Identity Assets
Brand SVGs, transparent PNGs, `.ico` app icons, `brand-tokens.json`, `brand-kit.html`, and the social media kit are generated programmatically:
```powershell
uv run --directory C:\Users\harsh\Documents\AspirantAI python scripts/generate_brand_assets.py
```

## Verification Suite
Run the full multi-stack check before committing:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_all.ps1
```
Individual checks:
- **Python (V1 Desktop + V2 Ecosystem Backend):** `$env:QT_QPA_PLATFORM="offscreen"; $env:PYTHONPATH="."; uv run python -m pytest tests backend/tests -v`
- **Frontend:** `cd frontend && npx tsc --noEmit && npm run build`
- **Desktop Electron Syntax:** `node -c desktop/electron/main.js && node -c desktop/electron/preload.js`
- **Mobile Flutter (when Flutter SDK is installed):** `cd mobile && flutter pub get && flutter analyze && flutter test`
