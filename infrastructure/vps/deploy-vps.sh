#!/usr/bin/env bash
set -euo pipefail

cd /opt/aspirant-ai
docker compose -f infrastructure/docker-compose.yml pull
docker compose -f infrastructure/docker-compose.yml up -d --build
docker compose -f infrastructure/docker-compose.yml exec -T backend sh -c "cd /app/backend && alembic upgrade head"
echo "VPS deployment updated cleanly."
