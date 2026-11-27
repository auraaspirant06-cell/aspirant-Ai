"""FastAPI application entrypoint for the Aspirant AI Ecosystem backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import EcosystemSettings, get_settings
from backend.app.core.container import EcosystemContainer
from backend.app.core.security import SecurityHeadersMiddleware


def create_app(settings: EcosystemSettings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    container = EcosystemContainer(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await container.db.create_all()
        yield
        await container.cache.close()
        await container.db.dispose()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        description="Unified FastAPI + Clean Architecture backend for NOVA, MJ, and MAX.",
        lifespan=lifespan,
    )
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        settings=cfg,
        rate_limiter=container.rate_limiter,
    )
    app.include_router(api_router, prefix=cfg.api_v1_prefix)

    @app.get("/")
    async def root() -> dict:
        return {
            "name": cfg.app_name,
            "tagline": "Intelligence Beyond Assistance",
            "docs": "/docs",
            "health": f"{cfg.api_v1_prefix}/health",
        }

    return app


app = create_app()
