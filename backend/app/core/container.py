"""Dependency injection container for backend core, AI layer, memory, and agents."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.ai.rag import RAGPipeline
from backend.app.ai.router import MultiModelAIRouter, ToolRegistry
from backend.app.ai.vector_store import UnifiedVectorStore, build_vector_store
from backend.app.core.config import EcosystemSettings, get_settings
from backend.app.core.database import DatabaseManager
from backend.app.core.security import (
    EncryptionAtRest,
    JWTService,
    SlidingWindowRateLimiter,
)
from backend.app.infrastructure.cache.redis_client import CacheStore
from backend.app.infrastructure.repositories.sqlalchemy_repos import (
    SQLAlchemyAgentRunRepository,
    SQLAlchemyAuditRepository,
    SQLAlchemyMemoryRepository,
    SQLAlchemyProductivityRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyUserRepository,
)
from backend.app.memory.memory_service import MemoryService
from backend.app.services.audit_service import AuditService
from backend.app.services.auth_service import AuthService
from backend.app.services.productivity_service import ProductivityService


class EcosystemContainer:
    """Holds singleton infrastructure and constructs request-scoped service bundles."""

    def __init__(self, settings: EcosystemSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = DatabaseManager(self.settings.database_url, echo=self.settings.database_echo)
        self.crypto = EncryptionAtRest(self.settings.encryption_master_key or self.settings.jwt_secret_key)
        self.jwt = JWTService(self.settings)
        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests=self.settings.rate_limit_requests,
            window_seconds=self.settings.rate_limit_window_seconds,
        )
        self.cache = CacheStore(self.settings.redis_url)
        self.vector_store: UnifiedVectorStore = build_vector_store(
            backend=self.settings.vector_backend,
            qdrant_url=self.settings.qdrant_url,
            qdrant_api_key=self.settings.qdrant_api_key,
            chroma_persist_dir=self.settings.chroma_persist_dir,
            chroma_host=self.settings.chroma_host,
        )
        self.tool_registry = ToolRegistry()
        self.ai_router = MultiModelAIRouter(self.settings, self.tool_registry)
        self.rag = RAGPipeline(self.vector_store, self.ai_router)

    def build_auth_service(self, session: AsyncSession) -> AuthService:
        return AuthService(
            users=SQLAlchemyUserRepository(session),
            sessions=SQLAlchemySessionRepository(session),
            audit=SQLAlchemyAuditRepository(session),
            jwt_service=self.jwt,
        )

    def build_audit_service(self, session: AsyncSession) -> AuditService:
        return AuditService(SQLAlchemyAuditRepository(session), self.settings)

    def build_productivity_service(self, session: AsyncSession) -> ProductivityService:
        return ProductivityService(SQLAlchemyProductivityRepository(session, self.crypto))

    def build_memory_service(self, session: AsyncSession) -> MemoryService:
        return MemoryService(
            memory_repo=SQLAlchemyMemoryRepository(session, self.crypto),
            user_repo=SQLAlchemyUserRepository(session),
            vector_store=self.vector_store,
            cache=self.cache,
        )

    def build_orchestrator(self, session: AsyncSession) -> AgentOrchestrator:
        return AgentOrchestrator(
            router=self.ai_router,
            rag=self.rag,
            memory=self.build_memory_service(session),
            run_repo=SQLAlchemyAgentRunRepository(session),
        )
