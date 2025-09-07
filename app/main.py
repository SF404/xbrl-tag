# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
from typing import Optional

from app.core.middleware import RequestContextMiddleware
from app.core.config import get_config
from app.core.errors import configure_exception_handlers
from app.core.logging import configure_logging
from app.api.router import api_router
from app.db.session import init_db, SessionLocal
from app.services.model_registry_service import ModelRegistry
from app.core.index_cache import index_cache
from langchain.schema import Document


def _copy_dir(src: Path, dst: Path) -> None:
    """Copy a directory tree (src → dst) if dst is missing or empty."""
    if not src.exists():
        raise FileNotFoundError(f"Active model path not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    if any(dst.iterdir()):
        return  # already copied
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _warm_taxonomy(taxonomy: str, registry: ModelRegistry) -> None:
    """Force-load FAISS index, run first encode(), and touch reranker."""
    vs = index_cache.load(taxonomy, registry.embedder, force_reload=True)
    # Ensure first encode path is hot
    _ = registry.embedder.embed_query("warmup")
    # Touch FAISS
    _ = vs.similarity_search_with_score("warmup", k=1)
    # Touch reranker if present
    if registry.reranker:
        dummy = [Document(page_content="", metadata={"reference": "warmup-ref"})]
        _ = registry.reranker.rerank("warmup", dummy, top_k=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Readiness flag (don’t report ready until warm is done)
    app.state.is_ready = {"ok": False}

    registry = ModelRegistry()
    app.state.registry = registry

    db = SessionLocal()
    try:
        # 1) Find active model paths from DB
        emb_path_str, rer_path_str = registry.get_active_model_paths(db)
        emb_src = Path(emb_path_str)
        rer_src = Path(rer_path_str)

        # 2) Copy ONLY the active models to local /tmp (avoid gcsfuse first-touch at runtime)
        emb_dst = Path("/tmp/models/active_embedder")
        rer_dst = Path("/tmp/models/active_reranker")
        _copy_dir(emb_src, emb_dst)
        _copy_dir(rer_src, rer_dst)

        # 3) Load models from local copies (no DB/config changes)
        registry.load_models_from_local(emb_dst, rer_dst)
        print("[Startup] Active models loaded from local cache.")

        # 4) Warm ALL indices found on disk (no WARM_TAXONOMIES)
        for tax in index_cache.disk_indices:
            try:
                _warm_taxonomy(tax, registry)
            except Exception as e:
                print(f"[Warmup] taxonomy='{tax}' skipped: {e}")

        app.state.is_ready["ok"] = True
        print("Startup ...... [DONE]")
    except Exception as e:
        print(f"Error during startup: {e}")
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

    # Optional readiness endpoint (health can also read the same flag if you prefer)
    @app.get("/ready")
    def ready():
        return {"ready": bool(getattr(app.state, "is_ready", {"ok": False})["ok"])}

    return app


app = create_app()
