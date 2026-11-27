# Aspirant AI Ecosystem — System Architecture & Security Model

## 1. Dual-Runtime Architecture (Workstation + Cloud Ecosystem)

### A. Native Windows Workstation (`src/aspirant/`)
Runs as a single lean desktop process combining:
1. **PySide6 Dark Glassmorphic UI (`src/aspirant/ui/`)** — 13 real interactive views with tray controls and global `Ctrl+Alt+Shift+E` Emergency Stop.
2. **Loopback FastAPI Daemon (`src/aspirant/server/`)** — bound strictly to `127.0.0.1` with DPAPI Bearer token and WebSocket `/ws/events`.
3. **Domain Engines**: `VoiceAssistantEngine` (Gemini 3.8 Live + Female TTS + 18+ Indian languages), `PC Control`, `Coding Studio`, `Gov Services` (19 `.gov.in` portals), `Image Studio`, `Video Studio`, and `File Manager`.

### B. Clean Architecture Ecosystem Platform (`backend/` & `apps/`)
1. **Domain Layer (`backend/app/domain/`)**: Pure Python dataclasses (`UserEntity`, `MemoryEntity`, `GoalEntity`, `HabitEntity`, `ReminderEntity`, `NoteEntity`, `AgentRunEntity`, `AuditEventEntity`) and repository `Protocol` contracts.
2. **Infrastructure Layer (`backend/app/infrastructure/`)**: Async SQLAlchemy 2.0 ORM tables managed via Alembic (`backend/migrations/`), transparent Fernet AES-HMAC encryption at rest for memories & notes, Redis cache/short-term ring with automatic in-memory fallback.
3. **AI & Memory Layer (`backend/app/ai/`, `backend/app/memory/`)**:
   - `MultiModelAIRouter` prioritizing Gemini API (`gemini-4-argon`, `gemini-4-carbon`, `gemini-3.5-flash-lite`), GPT-compatible endpoints, OpenAI tool calling schemas, and Ollama local fallback.
   - `UnifiedVectorStore` abstracting **Qdrant** (`qdrant-client`) and **Chroma** (`chromadb`) with embedded cosine fallback.
   - `MemoryService` coordinating short-term conversation turns, encrypted long-term memories, preferences, conversation recall, and RAG chunks across restarts.
4. **Multi-Agent Orchestrator (`backend/app/agents/`)**: Coordinates 7 collaborating specialists (`Research`, `Automation`, `Coding`, `Content`, `Productivity`, `Planning`, `Support`) sharing a single `SharedAgentContext`.
5. **Product Services (`apps/nova`, `apps/mj`, `apps/max`)**: Exposes product-specific business logic over REST API v1 and consumes Celery (`Redis`) background workers for embeddings, deep research, and mobile push notifications.

## 2. Security & Zero-Trust Controls
- **Passwords:** Argon2id (`argon2-cffi`).
- **Authentication:** Short-lived HS256 JWT access tokens + single-use rotatable refresh tokens (reuse triggers immediate revocation of all active sessions for that user).
- **Encryption at Rest:** Fernet (AES-128-CBC + HMAC-SHA256) on persisted memories and notes, plus DPAPI vault on Windows desktop.
- **Transport & Edge Protection:** Optional HTTPS enforcement + HSTS headers, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, sliding-window rate limiting (`429`), strict CORS allowlist, and PII-redacted security audit logs.
