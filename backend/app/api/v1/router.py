"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1 import analytics, auth, express, health, query_export, salary

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(express.router)
api_router.include_router(query_export.router)
api_router.include_router(salary.router)
api_router.include_router(analytics.router)
