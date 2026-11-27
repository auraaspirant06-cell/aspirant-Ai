"""Unified API v1 router aggregating core services and NOVA/MJ/MAX products."""

from __future__ import annotations

from fastapi import APIRouter

from apps.max.routes import router as max_router
from apps.mj.routes import router as mj_router
from apps.nova.routes import router as nova_router
from backend.app.api.v1 import agents, auth, health, memory, productivity, security


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(security.router)
api_router.include_router(memory.router)
api_router.include_router(agents.router)
api_router.include_router(productivity.router)
api_router.include_router(nova_router)
api_router.include_router(mj_router)
api_router.include_router(max_router)
