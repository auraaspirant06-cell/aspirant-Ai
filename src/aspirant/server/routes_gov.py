"""Modular FastAPI router for Indian Government Online Services (Phase 6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aspirant.gov.guardrails import GovGuardrailError, enforce_gov_guardrail
from aspirant.gov.portal_registry import GOV_SERVICES, list_services, lookup_state_portal
from aspirant.security.permissions import PermissionDeniedError


class GovFieldValidateRequest(BaseModel):
    service_id: str
    fields: dict[str, Any]


class GovDocExtractRequest(BaseModel):
    file_path: str


class GovResearchRequest(BaseModel):
    service_id: str
    question: str
    language_hint: str = "en"
    provider_id: str = "auto"


class GovActionGuardRequest(BaseModel):
    action: str
    url: str | None = None
    approval_id: str | None = None
    summary_target: str = ""


def create_gov_router(container: Any, auth_dependency: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/gov", dependencies=[auth_dependency])

    @router.get("/services")
    async def services_catalog() -> dict[str, Any]:
        return {"services": list_services(), "count": len(GOV_SERVICES)}

    @router.get("/state-portal")
    async def state_portal(state: str) -> dict[str, Any]:
        return lookup_state_portal(state)

    @router.post("/validate-fields")
    async def validate_fields(body: GovFieldValidateRequest) -> dict[str, Any]:
        try:
            return container.gov_assistant.validate_fields(body.service_id, body.fields)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/extract-document")
    async def extract_document(body: GovDocExtractRequest) -> dict[str, Any]:
        gkey = container.vault.get_secret("GEMINI_API_KEY") or container.settings.gemini_api_key
        try:
            return await container.gov_assistant.extract_document_transient(body.file_path, gemini_api_key=gkey)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/research")
    async def research_service(body: GovResearchRequest) -> dict[str, Any]:
        try:
            return await container.gov_assistant.research_guidance(
                body.service_id, body.question, body.language_hint, body.provider_id
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/open-portal")
    async def open_official_portal(url: str) -> dict[str, Any]:
        try:
            enforce_gov_guardrail("open_portal", url=url)
            return await container.browser_agent.open_tab(url, headless=False)
        except (GovGuardrailError, PermissionDeniedError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/guard-check")
    async def guard_check(body: GovActionGuardRequest) -> dict[str, Any]:
        try:
            res = enforce_gov_guardrail(
                body.action,
                url=body.url,
                approvals=container.approvals,
                approval_id=body.approval_id,
                summary_target=body.summary_target,
            )
            return res or {"status": "approved_to_proceed", "action": body.action}
        except GovGuardrailError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return router
