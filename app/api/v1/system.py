import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.config import get_config
from app.db.session import SessionLocal
from app.schemas.schemas import HealthResponse

router = APIRouter(prefix="/system")
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """
    Performs health checks on the application and its dependencies.

    This endpoint checks:
    - The application's startup readiness state.
    - The database connection.

    Returns a summary of the system's status.
    """
    config = get_config()

    # 1. Check application startup status
    # The `is_ready` state is set to True at the end of the startup lifespan event.
    app_status = (
        "ok" if getattr(request.app.state, "is_ready", {}).get("ok", False) else "starting"
    )

    # 2. Check database connectivity
    db_status = "up"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
        logger.error("Database health check failed", exc_info=True)

    # 3. Assemble and return the health response
    return HealthResponse(
        status=app_status,
        app_name=config.APP_NAME,
        version=config.APP_VERSION,
        environment=config.APP_ENV,
        backend=config.backend,
        database_status=db_status,
    )
