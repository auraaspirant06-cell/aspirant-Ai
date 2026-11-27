"""DevOps deployment planner across Azure, AWS, GCP, Oracle Cloud, Docker, K8s, Ubuntu VPS, DigitalOcean, Hetzner, Nginx, Cloudflare."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aspirant.deployment.planner import inspect_project_for_deployment, plan_deployment
from aspirant.deployment.ssh_verifier import verify_ssh_readiness


def build_deployment_guide(
    *,
    app_name: str = "aspirant-app",
    platform: str = "Ubuntu VPS",
    domain: str = "app.example.com",
    app_port: int = 8000,
    project_root: str | Path | None = None,
    execution_confirmed: bool = False,
) -> dict[str, Any]:
    """Generate full installation, Docker, systemd, UFW, Nginx proxy, SSL, rollback & monitoring configurations.

    Never claims deployment is complete unless *execution_confirmed* is explicitly True.
    """
    return plan_deployment(
        app_name=app_name,
        platform=platform,
        domain=domain,
        app_port=app_port,
        project_root=project_root,
        execution_confirmed=execution_confirmed,
    )


def inspect_and_check_ssh(
    *,
    project_root: str | Path | None = None,
    ssh_host: str = "",
    ssh_user: str = "ubuntu",
    ssh_key_path: str = "",
) -> dict[str, Any]:
    """Inspect workspace deployment readiness and verify SSH/PEM config safely without reading private key contents."""
    out: dict[str, Any] = {
        "ssh": verify_ssh_readiness(host=ssh_host, user=ssh_user, key_path=ssh_key_path),
    }
    if project_root is not None:
        out["project"] = inspect_project_for_deployment(project_root)
    return out
