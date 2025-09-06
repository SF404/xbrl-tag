from fastapi import APIRouter
from app.api.v1 import system, models, data

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
api_router.include_router(data.router, prefix="/data", tags=["Data"])