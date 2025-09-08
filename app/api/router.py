from fastapi import APIRouter

from app.api.v1 import (
    system,
    query,
    feedback,
    jobs,
    models,
    taxonomy,
)

api_router = APIRouter()

api_router.include_router(system.router, tags=["System"])
api_router.include_router(query.router, tags=["Query"])
api_router.include_router(feedback.router, tags=["Feedback"])
api_router.include_router(jobs.router, tags=["Jobs"])
api_router.include_router(models.router, tags=["Models"])
api_router.include_router(taxonomy.router, tags=["Taxonomy"])