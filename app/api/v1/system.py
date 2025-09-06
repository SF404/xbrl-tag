# api/health.py
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_config
from app.db.session import SessionLocal

router = APIRouter()

# ====== GET =======
@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    config = get_config()

    db_ok = False
    db_error = None
    try:
        with SessionLocal() as db:
            res = db.execute(text("SELECT 1"))
            _ = res.fetchone()
            db_ok = True
    except SQLAlchemyError as exc:
        db_error = str(exc)
    except Exception as exc:
        db_error = str(exc)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "app_name": config.APP_NAME,
        "version": config.APP_VERSION,
        "environment": config.APP_ENV,
        "backend": config.backend,
        "database": {
            "host": getattr(config, "DB_HOST", None),
            "port": getattr(config, "DB_PORT", None),
            "reachable": db_ok,
        },
    }

    if not db_ok:
        payload["database"]["error"] = db_error
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)

    return payload

