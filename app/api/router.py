from fastapi import APIRouter, Depends
from app.core.deps import require_access_level

from app.api.v1 import (
    auth,
    chatbot,
    feedback,
    jobs,
    models,
    query,
    system,
    taxonomy,
)

api_router = APIRouter()

# --- Public Routes ---
# Routes that do not require authentication
api_router.include_router(auth.router, tags=["Auth"])


# --- Protected Routes ---
# Routes that require authentication
api_router.include_router(system.router, tags=["System"], dependencies=[Depends(require_access_level(0))])
api_router.include_router(chatbot.router, tags=["Chatbot"], dependencies=[Depends(require_access_level(1))])
api_router.include_router(query.router, tags=["Query"], dependencies=[Depends(require_access_level(1))])
api_router.include_router(feedback.router, tags=["Feedback"], dependencies=[Depends(require_access_level(1))])
api_router.include_router(jobs.router, tags=["Jobs"], dependencies=[Depends(require_access_level(7))])
api_router.include_router(models.router, tags=["Models"], dependencies=[Depends(require_access_level(7))])
api_router.include_router(taxonomy.router, tags=["Taxonomy"], dependencies=[Depends(require_access_level(7))])
