# Troubleshooting Guide — ASPIRANT AI

## 1. Microphone Shows `MIC: NOT FOUND` or Silent Capture
- Open **Voice & ID** -> **Microphone Diagnostic Center** and click **Refresh Devices** -> **Reconnect Microphone**.
- Aspirant AI automatically prefers **Windows WASAPI** over **MME** and **DirectSound** and skips unsupported WDM-KS blocking capture hosts, resampling native 44.1/48 kHz streams to 16 kHz transparently.
- Ensure Windows Privacy settings allow microphone access (`Settings -> Privacy & security -> Microphone`).

## 2. Database Migration Failures
Run migrations explicitly from the repo root:
```powershell
uv run python -m alembic -c backend/alembic.ini upgrade head
powershell -ExecutionPolicy Bypass -File .\scripts\run_migrations.ps1
```

## 3. Gemini API Key or Rate Limit Issues
- Check `.env` or DPAPI vault (`Models` view) for a valid `GEMINI_API_KEY`.
- Verified active Gemini models used by Aspirant AI: `gemini-4-hydrogen`, `gemini-4-argon`, `gemini-4-carbon`, `gemini-3.8-flash`, `gemini-3.8-live`, `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, `gemini-nano-banana-2.1`, and `gemini-omni-1.2-flash`.
- Run offline at zero cloud cost anytime using Edge Neural TTS / Windows SAPI5 + Ollama local models (`1B-3B` recommended on 8 GB RAM).

## 4. Next.js Build or Port Conflicts
Stop stray local listeners cleanly and check health:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\health-check.ps1
```
