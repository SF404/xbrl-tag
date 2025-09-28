import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.api.router import api_router
from app.core.config import get_config
from app.core.errors import configure_exception_handlers
from app.core.logging import configure_logger
from app.core.middleware import AuthenticationMiddleware, RequestContextMiddleware
from app.db.migrate import run_migrations
from app.db.session import SessionLocal
from app.managers.jobs_manager import JobsManager
from app.services import ModelRegistry, VectorstoreService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database migrations
    run_migrations()
    # Application state initialization
    app.state.is_ready = {"ok": False}
    app.state.registry = ModelRegistry()
    app.state.vectorstore_service = VectorstoreService()
    app.state.jobs_manager = JobsManager()
    # Startup logic
    db = SessionLocal()
    try:
        app.state.registry.copy_active_models_to_local_runtime_and_load(db)
        app.state.vectorstore_service.warm_all_disk_indices(app.state.registry)
        app.state.is_ready["ok"] = True
        logging.info("Startup ...... [DONE]")
    except Exception as e:
        logging.error(f"Error during startup: {e}", exc_info=True)
    finally:
        db.close()
    yield
    logging.info("Shutdown ...... [DONE]")

def custom_openapi(app: FastAPI):
    """Custom OpenAPI schema that includes security definitions"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Apply security to all paths (optional)
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method in ["get", "post", "put", "delete", "patch"]:
                openapi_schema["paths"][path][method]["security"] = [
                    {"bearerAuth": []}
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, lifespan=lifespan)
    
    # Middleware setup
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(RequestContextMiddleware)
    
    # Configurations
    configure_logger()
    configure_exception_handlers(app)
    
    # API router
    app.include_router(
        router=api_router,
        prefix=config.API_PREFIX,
    )
    
    # Set custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)
    
    return app

app = create_app()