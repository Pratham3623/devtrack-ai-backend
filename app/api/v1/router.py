from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, organizations

api_router = APIRouter()

# Include endpoint modules
api_router.include_router(health.router, tags=["Health & System Operations"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Security"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organization Governance"])
