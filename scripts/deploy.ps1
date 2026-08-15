# ==============================================================================
# DevTrack AI — PowerShell Production Deployment Script (deploy.ps1)
# Usage: .\scripts\deploy.ps1 [-Environment production]
# ==============================================================================

param(
    [string]$Environment = "production"
)

$ErrorActionPreference = "Stop"
$EnvFile = ".env.${Environment}"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting DevTrack AI Deployment [Environment: $Environment]" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Environment File Check
if (-not (Test-Path $EnvFile)) {
    if (Test-Path ".env.production.example") {
        Write-Host "⚠️ Warning: $EnvFile not found. Creating from .env.production.example..." -ForegroundColor Yellow
        Copy-Item ".env.production.example" $EnvFile
        Write-Host "❗ Please edit $EnvFile with production passwords/secrets before continuing." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "❌ Error: Required environment file $EnvFile missing." -ForegroundColor Red
        exit 1
    }
}

# 2. Build Docker Images
Write-Host "🔨 Building production Docker images..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml build api nginx

# 3. Start Database & Redis
Write-Host "🗄️ Starting PostgreSQL and Redis services..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml up -d db redis

# 4. Wait for PostgreSQL Health
Write-Host "⏳ Waiting for PostgreSQL database health..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 5. Run Database Migrations
Write-Host "🔄 Running Alembic database migrations..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 6. Launch Full Stack
Write-Host "🌐 Launching Application Stack..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml up -d api nginx prometheus grafana

# 7. Health Check
Write-Host "🩺 Verifying application health..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

try {
    $res = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -Method Get
    if ($res.status -eq "healthy") {
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "🎉 SUCCESS: DevTrack AI Production Deployment Complete!" -ForegroundColor Green
        Write-Host "   - Health Status: $($res.status)" -ForegroundColor Green
        Write-Host "   - API Endpoint:  http://localhost:8000/api/v1/health" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
    } else {
        Write-Host "❌ Health check returned status: $($res.status)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Health check endpoint failed: $_" -ForegroundColor Red
}
