"""Bounded autonomous coding agent respecting project boundaries and approval gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aspirant.coding.generator import guard_project_file
from aspirant.coding.git_ops import GitCodeManager
from aspirant.coding.indexer import ProjectIndexer
from aspirant.coding.sandbox import CodingSandbox
from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import ApprovalQueue
from aspirant.security.permissions import Permission, PermissionManager


class AutonomousCoder:
    """Runs bounded read -> test -> diagnose -> patch -> verify loops within a project."""

    def __init__(
        self,
        indexer: ProjectIndexer,
        sandbox: CodingSandbox,
        git_mgr: GitCodeManager,
        providers: ProviderRegistry,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        approvals: ApprovalQueue,
    ) -> None:
        self.indexer = indexer
        self.sandbox = sandbox
        self.git_mgr = git_mgr
        self.providers = providers
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.approvals = approvals

    async def run_autonomous_task(
        self,
        project_root: str | Path,
        goal: str,
        target_file: str | None = None,
        max_iterations: int = 3,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute bounded autonomous coding loop with pre-execution boundary & approval checks."""
        self.permissions.require(Permission.READ, f"Inspect project for autonomous task", category="coding")
        self.permissions.require(Permission.WRITE, f"Edit code in {project_root}", category="coding")
        self.permissions.require(Permission.EXECUTE, f"Run tests in {project_root}", category="coding")

        root = Path(project_root).expanduser().resolve()
        index = self.indexer.index_project(root)

        # Require explicit approval before modifying an existing project unless pre-approved
        if not approval_id:
            req = self.approvals.request(
                category="coding",
                action="autonomous_code_task",
                target=f"{root.name}: {goal[:80]}",
                reason="Autonomous coding mode edits files and runs project tests inside this workspace.",
                rollback_hint="Use Git status/checkout or reversible backups to restore files.",
            )
            return {"status": "approval_required", "approval": req.to_dict(), "index": index}

        consumed = self.approvals.consume_approved(approval_id, expected_action="autonomous_code_task")
        if consumed is None:
            raise PermissionError("Valid approval_id is required to start autonomous coding.")

        steps: list[dict[str, Any]] = []
        bounded_iters = max(1, min(max_iterations, 5))

        for iteration in range(1, bounded_iters + 1):
            if self.permissions.is_emergency_stopped:
                steps.append({"iteration": iteration, "status": "halted_by_emergency_stop"})
                break

            test_res = self.sandbox.run_tests(root)
            steps.append(
                {
                    "iteration": iteration,
                    "phase": "test",
                    "passed": test_res["passed"],
                    "errors": test_res["parsed_errors"],
                }
            )
            if test_res["passed"]:
                review = self.git_mgr.pre_deploy_review(root)
                self.audit_logger.log(
                    category="coding",
                    action=f"Autonomous task passed tests on iteration {iteration} ({root.name})",
                    permission="EXECUTE",
                    decision="completed",
                    status="ok",
                )
                return {
                    "status": "completed",
                    "iterations": iteration,
                    "steps": steps,
                    "review": review,
                }

            # Attempt AI-assisted patch if target_file specified and provider available
            if target_file:
                safe_file = guard_project_file(root, target_file)
                current_src = safe_file.read_text(encoding="utf-8", errors="replace") if safe_file.exists() else ""
                allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
                try:
                    prompt = (
                        f"Goal: {goal}\nFile: {target_file}\n"
                        f"Current content:\n```python\n{current_src}\n```\n"
                        f"Test failures:\n{test_res['stdout']}\n{test_res['stderr']}\n"
                        "Return ONLY the complete corrected file content with no markdown fences."
                    )
                    resp = await self.providers.generate(
                        ChatRequest(messages=[ChatMessage("user", prompt)], temperature=0.1, max_tokens=2000),
                        allow_cloud=allow_cloud,
                    )
                    patched = resp.text.strip()
                    if patched.startswith("```"):
                        lines = patched.splitlines()
                        patched = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                    if patched:
                        safe_file.write_text(patched + "\n", encoding="utf-8")
                        steps.append({"iteration": iteration, "phase": "patched", "file": target_file})
                except Exception as exc:
                    steps.append({"iteration": iteration, "phase": "patch_skipped", "reason": str(exc)})
                    break
            else:
                break

        return {
            "status": "needs_review",
            "iterations": len(steps),
            "steps": steps,
            "review": self.git_mgr.pre_deploy_review(root),
        }
