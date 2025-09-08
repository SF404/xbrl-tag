import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_registry, get_vectorstore_service
from app.core.errors import AppException, ErrorCode
from app.repositories.setting import SettingRepository
from app.services.embedder_service import EmbedderService
from app.services.reranker_service import RerankerService
from app.schemas.schemas import (
    ActiveModelsResponse,
    UpdateSettingsRequest,
    MessageResponse,
    EmbedderResponse,
    RerankerResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/active_models", response_model=ActiveModelsResponse)
def get_active_models(db: Session = Depends(get_db)):
    try:
        s = SettingRepository(db).get_current()
        logger.info("Fetched active models", extra={
            "has_embedder": bool(s and s.embedder),
            "has_reranker": bool(s and s.reranker),
        })
        return ActiveModelsResponse(
            active_embedder=EmbedderResponse.model_validate(s.embedder, from_attributes=True) if s and s.embedder else None,
            active_reranker=RerankerResponse.model_validate(s.reranker, from_attributes=True) if s and s.reranker else None,
        )
    except Exception as e:
        logger.error("Failed to fetch active models", exc_info=True)
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR, str(e), status_code=500)


@router.patch("/active_models", response_model=ActiveModelsResponse)
def update_active_models(payload: UpdateSettingsRequest, db: Session = Depends(get_db)):
    repo = SettingRepository(db)
    try:
        logger.info("Updating active models", extra={
            "active_embedder_id": payload.active_embedder_id,
            "active_reranker_id": payload.active_reranker_id,
        })
        repo.set_active(embedder_id=payload.active_embedder_id, reranker_id=payload.active_reranker_id)
        db.commit()
        s = repo.get_current()
        logger.info("Updated active models", extra={
            "has_embedder": bool(s and s.embedder),
            "has_reranker": bool(s and s.reranker),
        })
        return ActiveModelsResponse(
            active_embedder=EmbedderResponse.model_validate(s.embedder, from_attributes=True) if s and s.embedder else None,
            active_reranker=RerankerResponse.model_validate(s.reranker, from_attributes=True) if s and s.reranker else None,
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to update active models", exc_info=True)
        # throw just the actual message via your AppException
        raise AppException(ErrorCode.DB_ERROR, str(e), status_code=500)


@router.post("/reload_models", response_model=MessageResponse)
def reload_models(
    db: Session = Depends(get_db),
    registry = Depends(get_registry),
    vectorstore = Depends(get_vectorstore_service),
):
    try:
        logger.info("Reloading models and warming indices")
        registry.copy_active_models_to_local_runtime_and_load(db)
        vectorstore.warm_all_disk_indices(registry)
        logger.info("Models reloaded and indices warmed")
        return MessageResponse(message="Models reloaded and indices warmed.")
    except Exception as e:
        logger.error("Failed to reload models", exc_info=True)
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR, str(e), status_code=500)


@router.get("/embedders", response_model=List[EmbedderResponse])
def list_embedders(db: Session = Depends(get_db)):
    try:
        items = EmbedderService(db).list()
        logger.info("Listed embedders", extra={"count": len(items)})
        return [EmbedderResponse.model_validate(x, from_attributes=True) for x in items]
    except Exception as e:
        logger.error("Failed to list embedders", exc_info=True)
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR, str(e), status_code=500)


@router.get("/rerankers", response_model=List[RerankerResponse])
def list_rerankers(db: Session = Depends(get_db)):
    try:
        items = RerankerService(db).list()
        logger.info("Listed rerankers", extra={"count": len(items)})
        return [RerankerResponse.model_validate(x, from_attributes=True) for x in items]
    except Exception as e:
        logger.error("Failed to list rerankers", exc_info=True)
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR, str(e), status_code=500)


@router.delete("/embedders/{id}", response_model=MessageResponse)
def delete_embedder(id: int, db: Session = Depends(get_db)):
    setting = SettingRepository(db).get_current()
    if setting and setting.active_embedder_id == id:
        logger.warning("Attempted to delete active embedder", extra={"embedder_id": id})
        raise AppException(ErrorCode.VALIDATION_ERROR, "Cannot delete the active embedder.", status_code=409)
    try:
        deleted = EmbedderService(db).delete(id)
        if not deleted:
            logger.warning("Embedder not found for delete", extra={"embedder_id": id})
            raise AppException(ErrorCode.NOT_FOUND, "Embedder not found", status_code=404)
        logger.info("Embedder deleted", extra={"embedder_id": id})
        return MessageResponse(message="Deleted.")
    except AppException:
        raise
    except Exception as e:
        logger.error("Failed to delete embedder", exc_info=True)
        raise AppException(ErrorCode.DB_ERROR, str(e), status_code=500)


@router.delete("/rerankers/{id}", response_model=MessageResponse)
def delete_reranker(id: int, db: Session = Depends(get_db)):
    setting = SettingRepository(db).get_current()
    if setting and setting.active_reranker_id == id:
        logger.warning("Attempted to delete active reranker", extra={"reranker_id": id})
        raise AppException(ErrorCode.VALIDATION_ERROR, "Cannot delete the active reranker.", status_code=409)
    try:
        deleted = RerankerService(db).delete(id)
        if not deleted:
            logger.warning("Reranker not found for delete", extra={"reranker_id": id})
            raise AppException(ErrorCode.NOT_FOUND, "Reranker not found", status_code=404)
        logger.info("Reranker deleted", extra={"reranker_id": id})
        return MessageResponse(message="Deleted.")
    except AppException:
        raise
    except Exception as e:
        logger.error("Failed to delete reranker", exc_info=True)
        raise AppException(ErrorCode.DB_ERROR, str(e), status_code=500)
