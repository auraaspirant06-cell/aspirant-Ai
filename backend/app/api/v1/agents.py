"""Multi-agent orchestration endpoints for the 7 collaborative Aspirant AI agents."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthenticatedPrincipal, get_container, get_current_user, get_db_session
from backend.app.core.container import EcosystemContainer
from backend.app.domain.entities import AgentRole, ProductSource


router = APIRouter(prefix="/agents", tags=["Multi-Agent Orchestration"])


class AgentExecuteRequest(BaseModel):
    objective: str = Field(min_length=2)
    source_app: ProductSource = ProductSource.NOVA
    agents: list[AgentRole] | None = None


@router.get("/catalog")
async def agent_catalog(
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    orch = container.build_orchestrator(session)
    return {"agents": orch.catalog()}


@router.post("/execute")
async def execute_agents(
    body: AgentExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    orch = container.build_orchestrator(session)
    run = await orch.execute_objective(
        user_id=principal.user.id,
        objective=body.objective,
        source_app=body.source_app,
        requested_agents=body.agents,
    )
    return {
        "run_id": run.id,
        "objective": run.objective,
        "source_app": run.source_app.value,
        "selected_agents": run.selected_agents,
        "plan_steps": run.plan_steps,
        "final_output": run.final_output,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/runs")
async def list_agent_runs(
    limit: int = 20,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    container: EcosystemContainer = Depends(get_container),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    orch = container.build_orchestrator(session)
    runs = await orch._runs.list_runs(principal.user.id, limit=min(100, max(1, limit)))
    return {
        "runs": [
            {
                "run_id": r.id,
                "objective": r.objective,
                "source_app": r.source_app.value,
                "selected_agents": r.selected_agents,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
    }
