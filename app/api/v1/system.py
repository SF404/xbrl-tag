from fastapi import APIRouter, Request
import logging
from sqlalchemy import text

from app.schemas.schemas import HealthResponse
from app.core.config import get_config
from app.db.session import SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    config = get_config()

    # DB health check
    db_status = "up"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
        logger.error("Database health check failed", exc_info=True)

    status = "ok" if getattr(request.app.state, "is_ready", {}).get("ok", False) else "starting"

    return HealthResponse(
        status=status,
        app_name=config.APP_NAME,
        version=config.APP_VERSION,
        environment=config.APP_ENV,
        backend=config.backend,
        database_status=db_status,
    )
