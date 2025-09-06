from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from app.api.v1 import system, models, data, query

api_router = APIRouter()

@api_router.get("/")
def root():
    return RedirectResponse(url="/health")

api_router.include_router(system.router, tags=["System"])
api_router.include_router(query.router, tags=["Query"])
api_router.include_router(models.router, tags=["Models"])
api_router.include_router(data.router, tags=["Data"])