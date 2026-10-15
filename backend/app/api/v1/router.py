from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, clients, leads, campaigns, dashboard, imports, reports

api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
api_router.include_router(users.router, prefix='/users', tags=['Users'])
api_router.include_router(clients.router, prefix='/clients', tags=['Clients'])
api_router.include_router(leads.router, prefix='/leads', tags=['Leads'])
api_router.include_router(campaigns.router, prefix='/campaigns', tags=['Campaigns'])
api_router.include_router(dashboard.router, prefix='/dashboard', tags=['Dashboard'])
api_router.include_router(imports.router, prefix='/imports', tags=['Imports'])
api_router.include_router(reports.router, prefix='/reports', tags=['Reports'])
