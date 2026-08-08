from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, issues, organizations, projects

api_router = APIRouter()

# Include endpoint modules
api_router.include_router(health.router, tags=["Health & System Operations"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Security"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organization Governance"])

# Projects: templates at /projects, org-scoped project routes at /organizations
api_router.include_router(projects.templates_router, prefix="/projects", tags=["Project Management Engine"])
api_router.include_router(projects.org_router, prefix="/organizations", tags=["Project Management Engine"])

# Issues: mounted under /organizations/{org_id}/projects/{project_id}/issues
api_router.include_router(issues.router, prefix="/organizations", tags=["Issue Tracking Engine"])



