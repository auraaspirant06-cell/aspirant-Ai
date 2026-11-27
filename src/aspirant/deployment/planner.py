"""Guarded multi-provider deployment blueprint generator for Azure, AWS, Ubuntu VPS, DigitalOcean, Hetzner, Docker, K8s."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aspirant.personality.system_prompt import EXTENDED_DEVOPS_PLATFORMS, SUPPORTED_DEVOPS_PLATFORMS


@dataclass(frozen=True, slots=True)
class DeploymentPlan:
    platform: str
    app_name: str
    domain: str
    app_port: int
    detected_runtime: str
    dockerfile: str
    docker_compose: str
    systemd_unit: str
    nginx_config: str
    ufw_commands: list[str]
    ssl_command: str
    install_commands: list[str]
    rollback_commands: list[str]
    health_check_url: str
    deployment_executed: bool
    confirmation_required: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_project_for_deployment(project_root: str | Path) -> dict[str, Any]:
    """Inspect a workspace to detect stack, port, Dockerfile, .env.example, and start command."""
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project directory not found: {root}")

    has_dockerfile = (root / "Dockerfile").is_file()
    has_compose = (root / "docker-compose.yml").is_file() or (root / "infrastructure" / "docker-compose.yml").is_file()
    has_env_example = (root / ".env.example").is_file()

    runtime = "unknown"
    suggested_port = 8000
    start_cmd = "uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
    if (root / "frontend" / "package.json").is_file() or (root / "package.json").is_file():
        if (root / "pyproject.toml").is_file():
            runtime = "fullstack-python-nextjs"
        else:
            runtime = "nodejs"
            suggested_port = 3000
            start_cmd = "npm run start"
    elif (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        runtime = "python-fastapi"
        suggested_port = 8000
    elif (root / "go.mod").is_file():
        runtime = "go"
        suggested_port = 8080
        start_cmd = "./server"
    elif (root / "Cargo.toml").is_file():
        runtime = "rust"
        suggested_port = 8080
        start_cmd = "./target/release/app"

    return {
        "root": str(root),
        "runtime": runtime,
        "suggested_port": suggested_port,
        "start_command": start_cmd,
        "has_dockerfile": has_dockerfile,
        "has_compose": has_compose,
        "has_env_example": has_env_example,
        "secrets_safe": not ((root / ".env").is_file() and not (root / ".gitignore").is_file()),
    }


def plan_deployment(
    *,
    app_name: str = "aspirant-app",
    platform: str = "Azure",
    domain: str = "app.example.com",
    app_port: int = 8000,
    project_root: str | Path | None = None,
    execution_confirmed: bool = False,
) -> dict[str, Any]:
    """Generate production deployment plans across Azure, AWS EC2, Ubuntu VPS, DigitalOcean, Hetzner, K8s.

    Never claims remote deployment completed unless execution_confirmed is explicitly True.
    """
    plat = next(
        (p for p in EXTENDED_DEVOPS_PLATFORMS if p.lower() == platform.strip().lower()),
        platform.strip() or "Azure",
    )
    slug = "".join(c if c.isalnum() or c == "-" else "-" for c in app_name.strip().lower()).strip("-") or "aspirant-app"

    detected_runtime = "python-fastapi"
    if project_root is not None:
        inspected = inspect_project_for_deployment(project_root)
        detected_runtime = inspected["runtime"]

    provider_steps: list[str]
    if plat == "Azure":
        provider_steps = [
            f"az group create --name {slug}-rg --location centralindia",
            f"az vm create --resource-group {slug}-rg --name {slug}-vm --image Ubuntu2404 --admin-username ubuntu --generate-ssh-keys",
            f"az vm open-port --resource-group {slug}-rg --name {slug}-vm --port 443",
        ]
    elif plat == "AWS":
        provider_steps = [
            f"aws ec2 run-instances --image-id ami-0c55b159cbfafe1f0 --instance-type t3.small --key-name <KEY_PAIR> --security-groups {slug}-sg",
            f"aws ec2 authorize-security-group-ingress --group-name {slug}-sg --protocol tcp --port 443 --cidr 0.0.0.0/0",
        ]
    elif plat == "DigitalOcean":
        provider_steps = [
            f"doctl compute droplet create {slug} --image ubuntu-24-04-x64 --size s-2vcpu-4gb --region blr1",
        ]
    elif plat == "Hetzner":
        provider_steps = [
            f"hcloud server create --name {slug} --type cpx21 --image ubuntu-24.04",
        ]
    elif plat == "Kubernetes":
        provider_steps = [
            "kubectl apply -f k8s/deployment.yaml && kubectl apply -f k8s/service.yaml",
        ]
    else:
        provider_steps = [
            f"# Target host: {plat} (Ubuntu 24.04 LTS, non-root sudo user recommended)",
        ]

    install_commands = [
        *provider_steps,
        "sudo apt-get update && sudo apt-get upgrade -y",
        "curl -fsSL https://get.docker.com | sh",
        "sudo apt-get install -y nginx certbot python3-certbot-nginx ufw",
    ]
    ufw_commands = [
        "sudo ufw allow OpenSSH",
        "sudo ufw allow 'Nginx Full'",
        "sudo ufw --force enable",
    ]
    dockerfile = (
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        f"EXPOSE {app_port}\n"
        f'CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "{app_port}"]\n'
    )
    docker_compose = (
        "services:\n"
        f"  {slug}:\n"
        "    build: .\n"
        "    restart: unless-stopped\n"
        f"    ports:\n      - '127.0.0.1:{app_port}:{app_port}'\n"
        "    env_file:\n      - .env\n"
        "    healthcheck:\n"
        f"      test: ['CMD', 'curl', '-fsS', 'http://127.0.0.1:{app_port}/health']\n"
        "      interval: 30s\n      timeout: 5s\n      retries: 3\n"
    )
    systemd_unit = (
        "[Unit]\n"
        f"Description={slug} Aspirant AI Service\n"
        "After=docker.service network-online.target\n\n"
        "[Service]\n"
        f"WorkingDirectory=/opt/{slug}\n"
        "ExecStart=/usr/bin/docker compose up --remove-orphans\n"
        "ExecStop=/usr/bin/docker compose down\n"
        "Restart=always\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    nginx_config = (
        f"server {{\n    listen 80;\n    server_name {domain};\n\n"
        "    location / {\n"
        f"        proxy_pass http://127.0.0.1:{app_port};\n"
        "        proxy_http_version 1.1;\n"
        "        proxy_set_header Upgrade $http_upgrade;\n"
        "        proxy_set_header Connection 'upgrade';\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n}\n"
    )
    ssl_command = (
        f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos -m admin@{domain} --redirect"
    )
    rollback_commands = [
        f"cd /opt/{slug} && docker compose ps",
        f"cd /opt/{slug} && docker compose rollback || docker compose down && git checkout HEAD~1 && docker compose up -d --build",
    ]
    domain_setup = (
        f"1. Add DNS A record `{domain}` -> `<PUBLIC_SERVER_IP>` in Cloudflare/DNS provider.\n"
        "2. Enable HTTPS Redirect + HSTS after TLS certificate issuance."
    )
    env_setup = (
        "1. Copy `.env.example` to `.env` on the server with `chmod 600 .env`.\n"
        "2. Inject `DATABASE_URL`, `ASPIRANT_JWT_SECRET`, and AI API keys securely (never commit `.env`)."
    )
    monitoring_suggestions = [
        f"Poll `https://{domain}/health` every 60s.",
        "Stream container stdout logs and alert on 5xx spikes or RAM > 85%.",
        "Monitor TLS certificate expiry (< 21 days remaining).",
    ]

    status = "completed" if execution_confirmed else "awaiting_user_execution_confirmation"
    message = (
        f"Deployment verified complete for {slug} on {plat}."
        if execution_confirmed
        else (
            f"Prepared deployment configuration for {slug} on {plat}. "
            "Deployment NOT executed yet — review commands & confirm approval before running on target host."
        )
    )
    plan = DeploymentPlan(
        platform=plat,
        app_name=slug,
        domain=domain,
        app_port=app_port,
        detected_runtime=detected_runtime,
        dockerfile=dockerfile,
        docker_compose=docker_compose,
        systemd_unit=systemd_unit,
        nginx_config=nginx_config,
        ufw_commands=ufw_commands,
        ssl_command=ssl_command,
        install_commands=install_commands,
        rollback_commands=rollback_commands,
        health_check_url=f"https://{domain}/health",
        deployment_executed=execution_confirmed,
        confirmation_required=not execution_confirmed,
        status=status,
    )
    return {
        **plan.to_dict(),
        "supported_platforms": list(EXTENDED_DEVOPS_PLATFORMS),
        "message": message,
        # Backwards-compatible keys consumed by existing tests & routes
        "installation_commands": install_commands,
        "docker_configuration": docker_compose,
        "reverse_proxy_configuration": nginx_config,
        "ssl_setup": ssl_command,
        "domain_setup": domain_setup,
        "environment_setup": env_setup,
        "monitoring_suggestions": monitoring_suggestions,
    }
