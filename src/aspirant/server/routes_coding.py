"""Modular FastAPI router for Advanced Coding Studio (Phase 5)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aspirant.providers.base import ProviderError
from aspirant.security.permissions import Permission, PermissionDeniedError


class ProjectPathRequest(BaseModel):
    project_root: str


class ScaffoldRequest(BaseModel):
    target_dir: str
    template_id: str
    overwrite: bool = False


class GenerateCodeRequest(BaseModel):
    prompt: str
    language: str = "python"
    provider_id: str = "auto"


class ExplainCodeRequest(BaseModel):
    code: str
    language_mode: str = "hinglish"
    provider_id: str = "auto"


class GitBranchRequest(BaseModel):
    project_root: str
    branch_name: str


class GitCommitRequest(BaseModel):
    project_root: str
    message: str


class GitPushRequest(BaseModel):
    project_root: str
    remote: str = "origin"
    branch: str = "main"
    approval_id: str | None = None


class AutonomousCodeRequest(BaseModel):
    project_root: str
    goal: str
    target_file: str | None = None
    max_iterations: int = 3
    approval_id: str | None = None


def create_coding_router(container: Any, auth_dependency: Any) -> APIRouter:
    """Create the coding router bound to AppContainer."""
    router = APIRouter(prefix="/api/v1/coding", dependencies=[auth_dependency])

    @router.post("/index")
    async def index_project(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            container.permissions.require(
                Permission.READ,
                f"Index project {body.project_root}",
                category="coding",
            )
            return container.coding_indexer.index_project(body.project_root)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/scaffold")
    async def scaffold(body: ScaffoldRequest) -> dict[str, Any]:
        try:
            return container.coding_generator.scaffold_project(
                body.target_dir, body.template_id, overwrite=body.overwrite
            )
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/generate")
    async def generate(body: GenerateCodeRequest) -> dict[str, Any]:
        try:
            return await container.coding_generator.generate_code(
                body.prompt, language=body.language, provider_id=body.provider_id
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, ProviderError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/tests")
    async def run_tests(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(container.coding_sandbox.run_tests, body.project_root)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/syntax")
    async def check_syntax(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            return container.coding_sandbox.check_syntax(body.project_root)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/explain")
    async def explain(body: ExplainCodeRequest) -> dict[str, Any]:
        try:
            return await container.coding_explainer.explain_code(
                body.code, language_mode=body.language_mode, provider_id=body.provider_id
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/docs")
    async def generate_docs(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            md = container.coding_explainer.generate_markdown_docs(body.project_root)
            return {"markdown": md}
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/git/init")
    async def git_init(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            return container.git_mgr.init_repo(body.project_root)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/git/status")
    async def git_status(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            return container.git_mgr.status(body.project_root)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/git/branch")
    async def git_branch(body: GitBranchRequest) -> dict[str, Any]:
        try:
            return container.git_mgr.create_branch(body.project_root, body.branch_name)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/git/commit")
    async def git_commit(body: GitCommitRequest) -> dict[str, Any]:
        try:
            return container.git_mgr.commit_all(body.project_root, body.message)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/git/review")
    async def git_review(body: ProjectPathRequest) -> dict[str, Any]:
        try:
            return container.git_mgr.pre_deploy_review(body.project_root)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/git/push")
    async def git_push(body: GitPushRequest) -> dict[str, Any]:
        try:
            return await container.git_mgr.push_with_approval(
                body.project_root, remote=body.remote, branch=body.branch, approval_id=body.approval_id
            )
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/autonomous")
    async def run_autonomous(body: AutonomousCodeRequest) -> dict[str, Any]:
        try:
            return await container.autonomous_coder.run_autonomous_task(
                project_root=body.project_root,
                goal=body.goal,
                target_file=body.target_file,
                max_iterations=body.max_iterations,
                approval_id=body.approval_id,
            )
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return router
