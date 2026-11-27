# API Documentation — Aspirant AI Ecosystem v2.0

Base URL: `http://127.0.0.1:8000/api/v1`  
Interactive OpenAPI / Swagger Docs: `http://127.0.0.1:8000/docs`

All endpoints below (except `/health`, `/auth/register`, `/auth/login`, `/auth/refresh`, and `/nova/wake-word`) require `Authorization: Bearer <access_token>`.

## Health & Telemetry
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service status, active vector backend (`qdrant`/`chroma`/`memory`), and cache mode |

## Authentication & Sessions (`/auth`)
| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Create account (Argon2id hash), issue JWT access + rotating refresh token |
| `POST` | `/api/v1/auth/login` | Authenticate device session and emit tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate single-use refresh token (revokes all sessions on reuse) |
| `POST` | `/api/v1/auth/logout` | Revoke active refresh session |
| `GET` | `/api/v1/auth/me` | Return authenticated user profile & device ID |

## Security & Audit (`/security`)
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/security/posture` | Encryption, rate-limit, HTTPS, and provider status |
| `GET` | `/api/v1/security/audit-logs` | Recent PII-redacted security audit trail |

## Memory & Vector RAG (`/memory`)
| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/memory` | Store encrypted memory (`short_term`, `long_term`, `preference`, `knowledge`, `conversation`) + index vector |
| `GET` | `/api/v1/memory` | List stored memories optionally filtered by layer |
| `GET` | `/api/v1/memory/search?q=...` | Hybrid semantic search (Qdrant/Chroma + encrypted SQL store) |
| `GET` | `/api/v1/memory/recall?topic=...` | Combined user profile, preferences, short-term turns & semantic recall |
| `PUT` | `/api/v1/memory/preferences` | Merge adaptive preferences & user profile summary |
| `POST` | `/api/v1/memory/rag/ingest` | Chunk and embed knowledge documents |
| `POST` | `/api/v1/memory/rag/query` | Retrieve citations and generate grounded answer |

## 7-Agent Orchestration (`/agents`)
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/agents/catalog` | List all 7 specialist agents and scopes |
| `POST` | `/api/v1/agents/execute` | Execute multi-agent collaborative plan with shared `SharedAgentContext` |
| `GET` | `/api/v1/agents/runs` | List historical multi-agent orchestration runs |

## Productivity & Cross-Device Sync (`/productivity`)
| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/v1/productivity/sync` | Export unified snapshot (goals, habits, reminders, decrypted notes) |
| `POST` | `/api/v1/productivity/goals` | Upsert goal and milestones |
| `POST` | `/api/v1/productivity/habits` | Upsert habit or perform daily streak check-in |
| `POST` | `/api/v1/productivity/reminders` | Upsert smart reminder |
| `POST` | `/api/v1/productivity/notes` | Upsert encrypted note with automatic AI summary |

## Product APIs (`/nova`, `/mj`, `/max`)
- **NOVA (`/nova`):** `POST /wake-word`, `POST /clipboard/analyze`, `POST /screen/ocr`, `POST /command/evaluate`, `POST /voice/command`, `POST /workflow/run`
- **MJ (`/mj`):** `POST /chat`, `POST /document/understand`, `POST /email/assist`, `POST /calendar/analyze`, `POST /research/plan`
- **MAX (`/max`):** `POST /chat`, `POST /voice-command`, `GET /daily-plan`, `POST /push`, `POST /device-integration`, `POST /sync`
