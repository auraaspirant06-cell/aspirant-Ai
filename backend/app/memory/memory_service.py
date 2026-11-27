"""Multi-layered ecosystem memory system surviving restarts and cross-device switches."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.ai.vector_store import UnifiedVectorStore
from backend.app.domain.entities import (
    MemoryEntity,
    MemoryLayer,
    ProductSource,
    new_id,
    utc_now,
)
from backend.app.domain.repositories import MemoryRepository, UserRepository
from backend.app.infrastructure.cache.redis_client import CacheStore


class MemoryService:
    """Manages short-term turns, long-term encrypted memories, preferences, semantic search, and recall."""

    def __init__(
        self,
        *,
        memory_repo: MemoryRepository,
        user_repo: UserRepository,
        vector_store: UnifiedVectorStore,
        cache: CacheStore,
    ) -> None:
        self._repo = memory_repo
        self._users = user_repo
        self._vectors = vector_store
        self._cache = cache

    async def remember(
        self,
        *,
        user_id: str,
        content: str,
        layer: MemoryLayer = MemoryLayer.LONG_TERM,
        source_app: ProductSource = ProductSource.MJ,
        summary: str = "",
        tags: list[str] | None = None,
        importance: float = 0.65,
        metadata: dict | None = None,
    ) -> MemoryEntity:
        clean_summary = summary.strip() or content.strip()[:160]
        entity = MemoryEntity(
            id=new_id(),
            user_id=user_id,
            layer=layer,
            content=content.strip(),
            summary=clean_summary,
            source_app=source_app,
            tags=tags or [],
            importance=max(0.0, min(1.0, importance)),
            metadata=metadata or {},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        saved = await self._repo.add(entity)
        self._vectors.upsert(
            record_id=saved.id,
            user_id=user_id,
            text=f"{saved.summary}\n{saved.content}",
            metadata={
                "layer": saved.layer.value,
                "source_app": saved.source_app.value,
                "tags": ",".join(saved.tags),
            },
        )
        await self._cache.push_short_term_turn(
            f"st:{user_id}",
            {
                "id": saved.id,
                "layer": saved.layer.value,
                "source_app": saved.source_app.value,
                "summary": saved.summary,
                "created_at": saved.created_at.isoformat(),
            },
        )
        return saved

    async def record_conversation_turn(
        self,
        *,
        user_id: str,
        role: str,
        message: str,
        source_app: ProductSource = ProductSource.NOVA,
        persist_long_term: bool = True,
    ) -> dict:
        turn = {
            "role": role,
            "message": message,
            "source_app": source_app.value,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._cache.push_short_term_turn(f"conv:{user_id}", turn)
        if persist_long_term:
            await self.remember(
                user_id=user_id,
                content=f"[{role} @ {source_app.value}] {message}",
                layer=MemoryLayer.CONVERSATION,
                source_app=source_app,
                importance=0.55,
                tags=["conversation", source_app.value],
            )
        return turn

    async def get_short_term_context(self, user_id: str, limit: int = 12) -> list[dict]:
        return await self._cache.get_short_term_turns(f"conv:{user_id}", limit=limit)

    async def set_preferences(
        self, user_id: str, preferences: dict, profile_summary: str | None = None
    ) -> dict:
        user = await self._users.update_preferences(user_id, preferences, profile_summary)
        for key, value in preferences.items():
            await self.remember(
                user_id=user_id,
                content=f"User preference {key} = {value}",
                layer=MemoryLayer.PREFERENCE,
                source_app=ProductSource.MJ,
                tags=["preference", str(key)],
                importance=0.9,
            )
        return {
            "preferences": user.preferences if user else preferences,
            "profile_summary": user.profile_summary if user else (profile_summary or ""),
        }

    async def semantic_search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 8,
        layer: MemoryLayer | None = None,
    ) -> list[dict]:
        filters = {"layer": layer.value} if layer else None
        vector_hits = self._vectors.search(user_id=user_id, query=query, limit=limit, filters=filters)
        db_hits = await self._repo.search_text(user_id, query, limit=limit)

        merged: dict[str, dict] = {}
        for vh in vector_hits:
            merged[vh.id] = {
                "id": vh.id,
                "content": vh.text,
                "layer": vh.metadata.get("layer", "long_term"),
                "source_app": vh.metadata.get("source_app", "mj"),
                "score": round(vh.score, 4),
                "match_type": f"vector:{self._vectors.active_backend}",
            }
        for item in db_hits:
            if layer and item.layer != layer:
                continue
            existing = merged.get(item.id)
            if existing:
                existing["score"] = round(max(existing["score"], 0.85), 4)
                existing["content"] = item.content
            else:
                merged[item.id] = {
                    "id": item.id,
                    "content": item.content,
                    "layer": item.layer.value,
                    "source_app": item.source_app.value,
                    "score": round(item.importance, 4),
                    "match_type": "encrypted-db",
                }
        ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    async def recall_context_bundle(self, *, user_id: str, topic: str) -> dict:
        user = await self._users.get_by_id(user_id)
        short_term = await self.get_short_term_context(user_id, limit=8)
        semantic = await self.semantic_search(user_id=user_id, query=topic, limit=6)
        return {
            "user_profile": user.profile_summary if user else "",
            "preferences": user.preferences if user else {},
            "short_term_turns": short_term,
            "semantic_memories": semantic,
            "vector_backend": self._vectors.active_backend,
        }

    async def list_memories(
        self, user_id: str, *, layer: MemoryLayer | None = None, limit: int = 50
    ) -> list[MemoryEntity]:
        return await self._repo.list_for_user(user_id, layer=layer, limit=limit)

    async def forget(self, user_id: str, memory_id: str) -> bool:
        deleted = await self._repo.delete(user_id, memory_id)
        if deleted:
            self._vectors.delete(record_id=memory_id)
        return deleted
