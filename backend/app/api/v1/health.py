"""Health, readiness, and telemetry endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_container
from backend.app.core.container import EcosystemContainer


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(container: EcosystemContainer = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "service": container.settings.app_name,
        "version": container.settings.app_version,
        "environment": container.settings.environment,
        "vector_backend": container.vector_store.active_backend,
        "cache_mode": container.cache.mode,
        "products": ["nova", "mj", "max"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
