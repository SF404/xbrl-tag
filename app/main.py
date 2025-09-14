import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.middleware import RequestContextMiddleware
from app.core.config import get_config
from app.core.errors import configure_exception_handlers
from app.core.logging import configure_logger
from app.api.router import api_router
from app.db.session import SessionLocal
from app.db.migrate import run_migrations
from app.services import ModelRegistry, VectorstoreService
from app.managers.jobs_manager import JobsManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    run_migrations()
    
    app.state.is_ready = {"ok": False}

    registry = ModelRegistry()
    app.state.registry = registry

    app.state.vectorstore_service = VectorstoreService()
    app.state.jobs_manager = JobsManager()

    db = SessionLocal()
    try:
        registry.copy_active_models_to_local_runtime_and_load(db)
        app.state.vectorstore_service.warm_all_disk_indices(registry)
        app.state.is_ready["ok"] = True
        
        logging.info("Startup ...... [DONE]")
    except Exception as e:
        logging.info(f"Error during startup: {e}")
    finally:
        db.close()

    yield

    logging.info("Shutdown ...... [DONE]")


def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestContextMiddleware)
    
    configure_logger()
    configure_exception_handlers(app)

    app.include_router(
        router=api_router,
        prefix=config.API_PREFIX,
    )

    return app


app = create_app()
