"""Memory, preferences, conversation recall, and grounded RAG endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import MemoryLayer, ProductSource
from backend.app.workers.tasks import embed_memory_task


router = APIRouter(prefix="/memory", tags=["Memory & RAG"])


class RememberRequest(BaseModel):
    content: str = Field(min_length=1)
    layer: MemoryLayer = MemoryLayer.LONG_TERM
    source_app: ProductSource = ProductSource.MJ
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.7, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class PreferencesRequest(BaseModel):
    preferences: dict
    profile_summary: str | None = None


class RAGIngestRequest(BaseModel):
    title: str
    content: str
    source: str = "knowledge"


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=4, ge=1, le=15)


@router.post("")
async def store_memory(
    body: RememberRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    saved = await mem.remember(
        user_id=principal.user.id,
        content=body.content,
        layer=body.layer,
        source_app=body.source_app,
        summary=body.summary,
        tags=body.tags,
        importance=body.importance,
        metadata=body.metadata,
    )
    embed_memory_task.delay(principal.user.id, saved.id, len(saved.content))
    return {
        "id": saved.id,
        "layer": saved.layer.value,
        "source_app": saved.source_app.value,
        "summary": saved.summary,
        "tags": saved.tags,
        "created_at": saved.created_at.isoformat(),
    }


@router.get("")
async def list_memories(
    layer: MemoryLayer | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    items = await mem.list_memories(principal.user.id, layer=layer, limit=limit)
    return {
        "memories": [
            {
                "id": m.id,
                "layer": m.layer.value,
                "content": m.content,
                "summary": m.summary,
                "source_app": m.source_app.value,
                "tags": m.tags,
                "importance": m.importance,
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ]
    }


@router.get("/search")
async def search_memories(
    q: str = Query(min_length=1),
    limit: int = Query(default=8, ge=1, le=25),
    layer: MemoryLayer | None = None,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    hits = await mem.semantic_search(user_id=principal.user.id, query=q, limit=limit, layer=layer)
    return {"query": q, "results": hits}


@router.get("/recall")
async def recall_context(
    topic: str = Query(default="overview"),
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    return await mem.recall_context_bundle(user_id=principal.user.id, topic=topic)


@router.put("/preferences")
async def update_preferences(
    body: PreferencesRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    return await mem.set_preferences(principal.user.id, body.preferences, body.profile_summary)


@router.post("/rag/ingest")
async def ingest_knowledge(
    body: RAGIngestRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
) -> dict:
    res = container.rag.ingest_document(
        user_id=principal.user.id,
        title=body.title,
        content=body.content,
        source=body.source,
    )
    return {"document_id": res.document_id, "chunks": res.chunk_count, "backend": res.backend}


@router.post("/rag/query")
async def query_knowledge(
    body: RAGQueryRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
) -> dict:
    return await container.rag.query_grounded(
        user_id=principal.user.id,
        question=body.question,
        top_k=body.top_k,
    )


class ActionTrackRequest(BaseModel):
    action: str = Field(min_length=1)
    workflow_name: str | None = None
    device_preferences: dict | None = None


@router.post("/actions/track")
async def track_frequent_action(
    body: ActionTrackRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    return await mem.track_action_usage(
        user_id=principal.user.id,
        action=body.action,
        workflow_name=body.workflow_name,
        device_preferences=body.device_preferences,
    )


@router.get("/profile/smart")
async def smart_memory_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    mem = container.build_memory_service(session)
    return await mem.get_smart_profile(principal.user.id)
