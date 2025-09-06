from fastapi import APIRouter
from app.api.v1 import system, models, data, query, jobs

api_router = APIRouter()

api_router.include_router(system.router, tags=["System"])
api_router.include_router(query.router, tags=["Query"])
api_router.include_router(jobs.router, tags=["Jobs"])
api_router.include_router(models.router, tags=["Models"])
api_router.include_router(data.router, tags=["Data"])