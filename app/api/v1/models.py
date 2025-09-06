from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.entities import Setting, Embedder, Reranker
from app.schemas.settings import UpdateSettingsRequest
from app.core.deps import get_db, get_registry
from app.services.embedder_service import list_embedders, delete_embedder
from app.services.reranker_service import list_rerankers, delete_reranker  
from app.core.errors import AppException, ErrorCode

router = APIRouter()

# ====== GET =======
@router.get("/active_models")
def get_active_models(db: Session = Depends(get_db)):
    setting = db.query(Setting).first()
    
    if not setting:
        return {"embedder": None, "reranker": None}
    
    embedder = db.get(Embedder, setting.active_embedder_id)
    reranker = db.get(Reranker, setting.active_reranker_id)

    return {
        "settings_id": {
            "id": setting.id, 
            "active_embedder_id": setting.active_embedder_id, 
            "active_reranker_id": setting.active_reranker_id
        },
        "embedder": {
            "id": embedder.id, 
            "name": embedder.name, 
            "version": embedder.version, 
            "path": embedder.path
        },
        "reranker": {
            "id": reranker.id, 
            "name": reranker.name,  
            "version": reranker.version, 
            "path": reranker.path
        }
    }


@router.get("/embedders")
def get_embedders(db: Session = Depends(get_db)):
    return list_embedders(db)


@router.get("/rerankers")
def get_rerankers(db: Session = Depends(get_db)):
    return list_rerankers(db)


# ====== POST =======
@router.post("/reload_models")
def reload_models(db: Session = Depends(get_db), registry=Depends(get_registry)):
    registry.load_models(db)
    return {"message": f"Active models reloaded."}


# ====== PUT =======
@router.put("/settings")
def update_settings(req: UpdateSettingsRequest, db: Session = Depends(get_db)):
    setting = db.query(Setting).first()
    if not setting:
        setting = Setting(active_embedder_id=req.active_embedder_id, active_reranker_id=req.active_reranker_id)
        db.add(setting)
    else:
        setting.active_embedder_id = req.active_embedder_id
        setting.active_reranker_id = req.active_reranker_id
    db.commit()
    return {"message": "Settings updated successfully"}


# ====== DELETE =======
@router.delete("/embedders/{embedder_id}")
def remove_embedder(embedder_id: int, db: Session = Depends(get_db)):
    obj = delete_embedder(db, embedder_id)
    if not obj:
        raise AppException(ErrorCode.NOT_FOUND, "Embedder not found", status_code=404)
    return {"message": "Embedder deleted successfully"}


@router.delete("/rerankers/{reranker_id}")
def remove_reranker(reranker_id: int, db: Session = Depends(get_db)):
    obj = delete_reranker(db, reranker_id)
    if not obj:
        raise AppException(ErrorCode.NOT_FOUND, "Reranker not found", status_code=404)
    return {"message": "Reranker deleted successfully"}
