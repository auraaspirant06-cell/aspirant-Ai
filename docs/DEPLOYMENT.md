# Deployment Guide — Docker, Cloud, VPS & Cloudflare

## 1. Full Docker Compose Stack (`infrastructure/docker-compose.yml`)
Starts **PostgreSQL 16**, **Redis 7**, **Qdrant**, **Chroma**, **FastAPI Backend** (running `alembic upgrade head`), **Celery Worker**, and **Next.js Frontend**:
```bash
export GEMINI_API_KEY="your-key"
export ASPIRANT_JWT_SECRET="$(openssl rand -hex 32)"
export ASPIRANT_ENCRYPTION_KEY="$(openssl rand -hex 32)"
docker compose -f infrastructure/docker-compose.yml up -d --build
```
Check health at `http://127.0.0.1:8000/api/v1/health` and UI at `http://127.0.0.1:3000`.

## 2. Azure Container Apps (`infrastructure/azure/`)
Provision managed Azure Container Apps using the provided Bicep template:
```powershell
powershell -ExecutionPolicy Bypass -File .\infrastructure\azure\deploy-azure.ps1 -ResourceGroup aspirant-ai-rg -Location centralindia
```

## 3. Linux VPS (`infrastructure/vps/`)
1. Copy repository to `/opt/aspirant-ai` and configure `.env` (`ENFORCE_HTTPS=true`, PostgreSQL & Redis URLs).
2. Either install the systemd unit (`aspirant-api.service`) + `nginx-https.conf` (TLS 1.2/1.3 + HSTS) or deploy via `bash infrastructure/vps/deploy-vps.sh`.

## 4. Cloudflare Tunnel & Edge Proxy (`infrastructure/cloudflare/`)
- **Zero-Inbound-Port Tunnel:** Run `cloudflared tunnel --config infrastructure/cloudflare/cloudflared-config.yml run` to expose `api.aspirant.ai` and `app.aspirant.ai` securely without opening inbound router ports.
- **Edge Security Worker:** Deploy `worker-edge-proxy.ts` with `wrangler deploy` using `wrangler.toml` to enforce `Strict-Transport-Security` and `X-Content-Type-Options` at Cloudflare's edge.

## 5. GitHub Actions CI/CD (`.github/workflows/ci-cd.yml`)
Every push to `main` or `develop` validates:
1. Backend migrations & pytest suite
2. Next.js TypeScript typecheck & production build
3. Electron script syntax check
4. Flutter `analyze` & `test`
5. Container builds published to GHCR on `main`
