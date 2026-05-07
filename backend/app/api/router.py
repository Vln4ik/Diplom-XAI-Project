from fastapi import APIRouter

from app.api.routes import audit_logs, auth, documents, notifications, organizations, reports, requirements, risks, system

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(audit_logs.router)
api_router.include_router(organizations.router)
api_router.include_router(documents.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(requirements.router)
api_router.include_router(risks.router)
api_router.include_router(system.router)
