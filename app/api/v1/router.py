from fastapi import APIRouter
from app.api.v1.endpoints import auth, boards, comments, dependencies, health, issues, labels, organizations, projects, websockets

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

# Boards: mounted under /organizations/{org_id}/projects/{project_id}/boards
api_router.include_router(boards.router, prefix="/organizations", tags=["Kanban Board Engine"])

# Comments & Activity: mounted under /organizations/{org_id}/projects/{project_id}/issues/{issue_id}
api_router.include_router(comments.router, prefix="/organizations", tags=["Issue Comments & Activity Engine"])

# Labels: mounted under /organizations/{org_id}/projects/{project_id}/labels
api_router.include_router(labels.router, prefix="/organizations", tags=["Issue Labels Engine"])

# Dependencies & Subtasks: mounted under /organizations/{org_id}/projects/{project_id}/issues/{issue_id}
api_router.include_router(dependencies.router, prefix="/organizations", tags=["Subtasks & Dependencies Engine"])

# WebSockets: mounted under /organizations/{org_id}/projects/{project_id}/ws
api_router.include_router(websockets.router, prefix="/organizations", tags=["Real-Time Collaboration Engine"])



