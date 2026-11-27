"""Authentication and JWT refresh rotation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer


router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    device_name: str = "primary-desktop"
    device_platform: str = "windows"


class LoginRequest(BaseModel):
    email: str
    password: str
    device_name: str = "web-client"
    device_platform: str = "web"


class RefreshRequest(BaseModel):
    refresh_token: str


def _user_out(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "preferences": user.preferences,
        "profile_summary": user.profile_summary,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_auth_service(session)
    ip = request.client.host if request.client else "local"
    try:
        res = await svc.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            device_name=body.device_name,
            device_platform=body.device_platform,
            ip_address=ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "user": _user_out(res["user"]),
        "access_token": res["access_token"],
        "refresh_token": res["refresh_token"],
        "token_type": res["token_type"],
        "session_id": res["session_id"],
    }


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_auth_service(session)
    ip = request.client.host if request.client else "local"
    try:
        res = await svc.login(
            email=body.email,
            password=body.password,
            device_name=body.device_name,
            device_platform=body.device_platform,
            ip_address=ip,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {
        "user": _user_out(res["user"]),
        "access_token": res["access_token"],
        "refresh_token": res["refresh_token"],
        "token_type": res["token_type"],
        "session_id": res["session_id"],
    }


@router.post("/refresh")
async def refresh_tokens(
    body: RefreshRequest,
    request: Request,
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_auth_service(session)
    ip = request.client.host if request.client else "local"
    try:
        res = await svc.refresh(refresh_token=body.refresh_token, ip_address=ip)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {
        "user": _user_out(res["user"]),
        "access_token": res["access_token"],
        "refresh_token": res["refresh_token"],
        "token_type": res["token_type"],
        "session_id": res["session_id"],
    }


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    request: Request,
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    svc = container.build_auth_service(session)
    ip = request.client.host if request.client else "local"
    await svc.logout(refresh_token=body.refresh_token, ip_address=ip)
    return {"status": "logged_out"}


@router.get("/me")
async def me(principal: AuthenticatedPrincipal = Depends(get_current_user)) -> dict:
    return {"user": _user_out(principal.user), "device_id": principal.device_id}
