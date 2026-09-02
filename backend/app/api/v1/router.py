"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1 import (
    access,
    analytics,
    auth,
    express,
    health,
    operation_records,
    query_export,
    reimbursement,
    salary,
    suppliers,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(express.router)
api_router.include_router(query_export.router)
api_router.include_router(salary.router)
api_router.include_router(analytics.router)
api_router.include_router(reimbursement.router)
api_router.include_router(suppliers.router)
api_router.include_router(operation_records.router)
api_router.include_router(access.router)
