"""FastAPI dependency injection helpers for database sessions, container, and JWT auth."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import UserEntity
from backend.app.infrastructure.repositories.sqlalchemy_repos import SQLAlchemyUserRepository


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthenticatedPrincipal:
    user: UserEntity
    device_id: str | None = None


def get_container(request: Request) -> EcosystemContainer:
    return request.app.state.container


async def get_db_session(
    container: EcosystemContainer = Depends(get_container),
) -> AsyncIterator[AsyncSession]:
    async with container.db.session() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> AuthenticatedPrincipal:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer authentication token",
        )
    try:
        payload = container.jwt.decode_token(credentials.credentials, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

    user_id = str(payload.get("sub", ""))
    user = await SQLAlchemyUserRepository(session).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer active",
        )
    return AuthenticatedPrincipal(user=user, device_id=payload.get("device_id"))
