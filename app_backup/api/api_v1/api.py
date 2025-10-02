from fastapi import APIRouter
from .endpoints import auth, users, organizations, projects, tasks, subscriptions, teams, customers, items, proposals, invoices, analytics, websockets, files, notifications, automation

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(websockets.router, prefix="", tags=["websockets"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(automation.router, prefix="/automation", tags=["automation"])
