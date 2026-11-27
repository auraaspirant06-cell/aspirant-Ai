"""DevOps deployment planner across Azure, AWS, GCP, Oracle Cloud, Docker, K8s, Ubuntu VPS, Nginx, Cloudflare."""

from __future__ import annotations

from typing import Any

from aspirant.personality.system_prompt import SUPPORTED_DEVOPS_PLATFORMS


def build_deployment_guide(
    *,
    app_name: str = "aspirant-app",
    platform: str = "Ubuntu VPS",
    domain: str = "app.example.com",
    app_port: int = 8000,
    execution_confirmed: bool = False,
) -> dict[str, Any]:
    """Generate full installation, Docker, reverse proxy, SSL, DNS, env & monitoring configurations.

    Never claims deployment is complete unless *execution_confirmed* is explicitly True.
    """
    plat = next(
        (p for p in SUPPORTED_DEVOPS_PLATFORMS if p.lower() == platform.strip().lower()),
        platform.strip() or "Docker",
    )
    slug = app_name.strip().lower().replace(" ", "-") or "aspirant-app"

    install_commands = [
        "sudo apt-get update && sudo apt-get upgrade -y",
        "curl -fsSL https://get.docker.com | sh",
        "sudo apt-get install -y nginx certbot python3-certbot-nginx ufw",
        "sudo ufw allow 'Nginx Full' && sudo ufw allow OpenSSH && sudo ufw --force enable",
    ]
    if plat == "Kubernetes":
        install_commands.append("kubectl apply -f k8s/deployment.yaml && kubectl apply -f k8s/service.yaml")
    elif plat in {"AWS", "Azure", "Google Cloud", "Oracle Cloud"}:
        install_commands.append(f"# Provision compute/container instance on {plat} with ports 80 & 443 open.")

    docker_config = (
        "services:\n"
        f"  {slug}:\n"
        "    build: .\n"
        "    restart: unless-stopped\n"
        f"    ports:\n      - '127.0.0.1:{app_port}:{app_port}'\n"
        "    env_file:\n      - .env\n"
        "    healthcheck:\n"
        f"      test: ['CMD', 'curl', '-fsS', 'http://localhost:{app_port}/health']\n"
        "      interval: 30s\n      timeout: 5s\n      retries: 3\n"
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
    ssl_setup = (
        f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos -m admin@{domain}\n"
        "# If proxied behind Cloudflare, set Cloudflare SSL/TLS mode to 'Full (strict)'."
    )
    domain_setup = (
        f"1. Add DNS A record: `{domain}` -> `<PUBLIC_SERVER_IP>` in Cloudflare DNS.\n"
        "2. Enable HTTPS Redirect + Always Use HTTPS + HSTS after TLS certificate issuance."
    )
    env_setup = (
        "1. Store `.env` with `chmod 600 .env` on the server (never commit `.env` to Git).\n"
        "2. Provide `DATABASE_URL`, `JWT_SECRET`, and provider API keys via secret manager or `.env`."
    )
    monitoring_suggestions = [
        f"Poll `https://{domain}/health` every 60s (Uptime Kuma / Better Stack / CloudWatch).",
        "Stream container stdout logs to Grafana Loki / Cloud Logging with error-rate alerts.",
        "Monitor CPU, RAM (<85%), disk free space (>15%), and TLS certificate expiry (<21 days).",
    ]

    status = (
        f"Deployment verified complete for {slug} on {plat}."
        if execution_confirmed
        else (
            f"Prepared deployment configuration for {slug} on {plat}. "
            "Deployment NOT marked complete — confirm execution after running commands on target host."
        )
    )
    return {
        "platform": plat,
        "supported_platforms": list(SUPPORTED_DEVOPS_PLATFORMS),
        "domain": domain,
        "deployment_executed": execution_confirmed,
        "confirmation_required": not execution_confirmed,
        "status": "completed" if execution_confirmed else "awaiting_user_execution_confirmation",
        "message": status,
        "installation_commands": install_commands,
        "docker_configuration": docker_config,
        "reverse_proxy_configuration": nginx_config,
        "ssl_setup": ssl_setup,
        "domain_setup": domain_setup,
        "environment_setup": env_setup,
        "monitoring_suggestions": monitoring_suggestions,
    }
