from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager


from app.core.middleware import RequestContextMiddleware
from app.core.config import get_config
from app.core.errors import configure_exception_handlers
from app.core.logging import configure_logging
from app.api.router import api_router
from app.db.session import init_db, SessionLocal
from app.services.model_registry_service import ModelRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    registry = ModelRegistry()
    app.state.registry = registry
    try:
        db = SessionLocal()
        registry.load_models(db)
        print("Startup ...... [DONE]")
    except Exception as e:
        print(f"Error connecting to the database: {e}")
    finally:
        db.close()

    yield
    print("Shutdown ...... [DONE]")


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

    configure_exception_handlers(app)
    configure_logging("INFO")

    app.include_router(
        router=api_router,
        prefix=config.API_PREFIX,
    )
    
    @app.get("/")
    def root():
        return RedirectResponse(url="/api/v1/health")

    return app

app = create_app()





