#!/usr/bin/env bash
# ==============================================================================
# DevTrack AI — Automated Production Deployment Script (deploy.sh)
# Usage: ./scripts/deploy.sh [production|staging]
# ==============================================================================

set -euo pipefail

ENV="${1:-production}"
ENV_FILE=".env.${ENV}"

echo "============================================================"
echo "🚀 Starting DevTrack AI Deployment [Environment: ${ENV}]"
echo "============================================================"

# 1. Environment Verification
if [ ! -f "${ENV_FILE}" ]; then
  if [ -f ".env.production.example" ]; then
    echo "⚠️ Warning: ${ENV_FILE} not found. Creating from .env.production.example..."
    cp .env.production.example "${ENV_FILE}"
    echo "❗ Please edit ${ENV_FILE} with production passwords/secrets before continuing."
    exit 1
  else
    echo "❌ Error: Required environment file ${ENV_FILE} missing."
    exit 1
  fi
fi

# 2. Load Environment Variables
echo "📦 Loading environment configuration from ${ENV_FILE}..."
export $(grep -v '^#' "${ENV_FILE}" | xargs)

# 3. Build & Pull Latest Containers
echo "🔨 Building production Docker images..."
docker compose -f docker-compose.prod.yml build --no-cache api nginx

# 4. Start Infrastructure Services First (DB & Redis)
echo "🗄️ Starting PostgreSQL and Redis containers..."
docker compose -f docker-compose.prod.yml up -d db redis

# 5. Wait for Database Healthcheck
echo "⏳ Waiting for PostgreSQL database to be healthy..."
until docker compose -f docker-compose.prod.yml exec db pg_isready -U "${POSTGRES_USER:-devtrack_admin}" -d "${POSTGRES_DB:-devtrack_production_db}"; do
  sleep 2
done
echo "✅ PostgreSQL is healthy and accepting connections."

# 6. Execute Alembic Database Migrations
echo "🔄 Running Alembic database migrations..."
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 7. Start API, Nginx, and Telemetry Services
echo "🌐 Launching Application API, Nginx Reverse Proxy, and Telemetry..."
docker compose -f docker-compose.prod.yml up -d api nginx prometheus grafana

# 8. Verify Deployment Health
echo "🩺 Verifying system health status..."
sleep 5

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "FAILED")

if [ "${HEALTH_STATUS}" == "200" ]; then
  echo "============================================================"
  echo "🎉 SUCCESS: DevTrack AI Production Deployment Complete!"
  echo "   - Web App UI:  http://localhost:80 (or your domain)"
  echo "   - API Endpoint: http://localhost:8000/api/v1/health"
  echo "   - Prometheus:  http://localhost:9090"
  echo "   - Grafana:     http://localhost:3000"
  echo "============================================================"
else
  echo "❌ Error: System health check failed with HTTP ${HEALTH_STATUS}."
  docker compose -f docker-compose.prod.yml logs --tail=50 api
  exit 1
fi
