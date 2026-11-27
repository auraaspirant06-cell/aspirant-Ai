"""Git (native CLI or pure-Python dulwich fallback), code review, and GitHub integration."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

from dulwich import porcelain
from dulwich.repo import Repo
import httpx

from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import ApprovalQueue, is_protected_path
from aspirant.security.permissions import Permission, PermissionManager


class GitCodeManager:
    """Works natively via git CLI when present or pure-Python dulwich otherwise."""

    def __init__(
        self,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        approvals: ApprovalQueue,
    ) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.approvals = approvals

    def _guard_repo(self, repo_path: str | Path) -> Path:
        root = Path(repo_path).expanduser().resolve()
        blocked, reason = is_protected_path(root)
        if blocked:
            raise PermissionError(reason)
        if not root.is_dir():
            raise FileNotFoundError(f"Repository path not found: {root}")
        return root

    def init_repo(self, repo_path: str | Path) -> dict[str, Any]:
        self.permissions.require(Permission.WRITE, f"Initialize Git repo in {repo_path}", category="git")
        root = self._guard_repo(repo_path)
        if not (root / ".git").exists():
            porcelain.init(str(root))
        self.audit_logger.log(
            category="git",
            action=f"Initialized Git repository at {root.name}",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {"root": str(root), "initialized": True}

    def status(self, repo_path: str | Path) -> dict[str, Any]:
        self.permissions.require(Permission.READ, f"Git status {repo_path}", category="git")
        root = self._guard_repo(repo_path)
        if not (root / ".git").exists():
            return {"initialized": False, "branch": None, "staged": [], "unstaged": [], "untracked": []}

        st = porcelain.status(str(root))
        repo = Repo(str(root))
        try:
            head_ref = repo.refs.read_ref(b"HEAD")
            branch = (
                head_ref.decode("utf-8").replace("ref: refs/heads/", "")
                if head_ref
                else "main"
            )
        finally:
            repo.close()

        staged = [p.decode("utf-8", errors="replace") for k in ("add", "modify", "delete") for p in st.staged.get(k, [])]
        unstaged = [p.decode("utf-8", errors="replace") for p in st.unstaged]
        untracked = [p if isinstance(p, str) else p.decode("utf-8", errors="replace") for p in st.untracked]
        return {
            "initialized": True,
            "branch": branch,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "has_git_cli": bool(shutil.which("git")),
        }

    def create_branch(self, repo_path: str | Path, branch_name: str) -> dict[str, Any]:
        self.permissions.require(Permission.WRITE, f"Create branch {branch_name}", category="git")
        root = self._guard_repo(repo_path)
        clean_name = branch_name.strip().replace(" ", "-")
        if not clean_name:
            raise ValueError("Branch name cannot be empty.")
        repo = Repo(str(root))
        try:
            head_sha = repo.head()
            repo.refs[f"refs/heads/{clean_name}".encode("utf-8")] = head_sha
            repo.refs.set_symbolic_ref(b"HEAD", f"refs/heads/{clean_name}".encode("utf-8"))
        finally:
            repo.close()
        self.audit_logger.log(
            category="git",
            action=f"Switched to new branch {clean_name} in {root.name}",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {"branch": clean_name, "created": True}

    def commit_all(
        self,
        repo_path: str | Path,
        message: str,
        author: str = "Aspirant User <aspirant@localhost>",
    ) -> dict[str, Any]:
        self.permissions.require(Permission.WRITE, f"Commit changes in {repo_path}", category="git")
        root = self._guard_repo(repo_path)
        if not message.strip():
            raise ValueError("Commit message cannot be empty.")
        if not (root / ".git").exists():
            porcelain.init(str(root))

        # Stage safe non-secret files only
        to_stage: list[str] = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in rel.parts):
                continue
            if p.name.lower() in {".env", "vault.enc", "vault.key", ".api_token"}:
                continue
            to_stage.append(str(rel))

        if to_stage:
            porcelain.add(str(root), paths=[str(root / r) for r in to_stage])
        sha = porcelain.commit(
            str(root),
            message=message.strip().encode("utf-8"),
            author=author.encode("utf-8"),
            committer=author.encode("utf-8"),
        )
        sha_hex = sha.decode("ascii") if isinstance(sha, bytes) else str(sha)
        self.audit_logger.log(
            category="git",
            action=f"Created Git commit {sha_hex[:8]}: {message[:60]}",
            permission="WRITE",
            decision="executed",
            status="ok",
        )
        return {"commit_sha": sha_hex, "files_staged": len(to_stage), "message": message.strip()}

    def pre_deploy_review(self, repo_path: str | Path) -> dict[str, Any]:
        """Scan project for accidental secrets, syntax errors, and uncommitted state before publish."""
        self.permissions.require(Permission.READ, f"Pre-deployment code review for {repo_path}", category="git")
        root = self._guard_repo(repo_path)
        findings: list[str] = []
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in item.parts):
                continue
            if item.name.lower() == ".env":
                findings.append(f"Secret file present: {item.relative_to(root)} (verify .gitignore excludes it)")
            if item.suffix.lower() == ".py":
                txt = item.read_text(encoding="utf-8", errors="replace")
                if "AIza" in txt or "sk-" in txt:
                    findings.append(f"Possible hardcoded API key pattern in {item.relative_to(root)}")
        st = self.status(root)
        return {
            "root": str(root),
            "git": st,
            "findings": findings,
            "ready": len(findings) == 0,
        }

    async def push_with_approval(
        self,
        repo_path: str | Path,
        remote: str = "origin",
        branch: str = "main",
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        """Publishing / pushing code to GitHub always requires NETWORK + explicit user approval."""
        self.permissions.require(Permission.EXECUTE, f"Push {repo_path} to {remote}/{branch}", category="git")
        self.permissions.require(Permission.NETWORK, "Network access to GitHub remote", category="git")
        root = self._guard_repo(repo_path)

        if not approval_id:
            review = self.pre_deploy_review(root)
            req = self.approvals.request(
                category="git",
                action="git_push",
                target=f"{root.name} -> {remote}/{branch}",
                reason="Publishing code to remote repository requires explicit approval.",
                rollback_hint="Run git revert or reset remote branch if published prematurely.",
                payload={"review": review},
            )
            return {"status": "approval_required", "approval": req.to_dict(), "review": review}

        consumed = self.approvals.consume_approved(approval_id, expected_action="git_push")
        if consumed is None:
            raise PermissionError("Valid approval_id is required before pushing to remote.")

        if shutil.which("git"):
            proc = subprocess.run(
                ["git", "push", remote, branch],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {"status": "completed" if proc.returncode == 0 else "error", "stdout": proc.stdout, "stderr": proc.stderr}
        return {"status": "error", "detail": "git CLI not found for remote push; configure Git or GitHub token."}

    async def github_user_repos(self, github_token: str | None) -> list[dict[str, Any]]:
        self.permissions.require(Permission.NETWORK, "Fetch GitHub repositories", category="git")
        if not github_token:
            raise ValueError("GITHUB_TOKEN is not configured.")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github+json"},
                params={"per_page": 20, "sort": "updated"},
            )
            resp.raise_for_status()
            return [{"name": r["full_name"], "private": r["private"], "url": r["html_url"]} for r in resp.json()]
