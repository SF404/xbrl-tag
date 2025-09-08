import logging
import numpy as np
from pathlib import Path
from typing import Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from langchain.schema import Document

from app.core.config import get_config
from app.utils import copy_dir
from app.repositories import SettingRepository, EmbedderRepository, RerankerRepository
from app.models import Setting

try:
    from langchain.embeddings.base import Embeddings
except Exception:
    from langchain.embeddings import Embeddings
    
logger = logging.getLogger(__name__)



class SentenceTransformerEmbedder(Embeddings):
    def __init__(self, model):
        self.model = model

    def embed_query(self, text: str) -> List[float]:
        vec = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vec, dtype=np.float32).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vecs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32).tolist()

    def __call__(self, text_or_texts: Any):
        if isinstance(text_or_texts, (list, tuple)):
            return self.embed_documents(list(text_or_texts))
        return self.embed_query(text_or_texts)


class CrossEncoderReranker:
    def __init__(self, model: Any, normalize_method: str = "softmax"):
        self.model = model
        self.normalize_method = normalize_method

    def rerank(self, query: str, docs: List[Document], top_k: int = 5):
        pairs = [(query, d.metadata.get("reference", "")) for d in docs]
        raw = self.model.predict(pairs, show_progress_bar=False)

        if self.normalize_method == "softmax":
            exp_scores = np.exp(raw - np.max(raw))
            scores = exp_scores / exp_scores.sum()
        elif self.normalize_method == "sigmoid":
            scores = 1 / (1 + np.exp(-raw))
        elif self.normalize_method == "minmax":
            min_s, max_s = np.min(raw), np.max(raw)
            scores = (raw - min_s) / (max_s - min_s) if max_s != min_s else np.ones_like(raw) * 0.5
        else:
            scores = raw

        ranked = list(zip(docs, scores))
        return sorted(ranked, key=lambda x: x[1], reverse=True)[:top_k]


class ModelRegistry:
    def __init__(self):
        self.config = get_config()
        self.embedder = None
        self.reranker = None


    def load_models_from_path(self, embedder_dir: Path, reranker_dir: Path) -> None:
        from sentence_transformers import SentenceTransformer, CrossEncoder

        embedder_model = SentenceTransformer(str(embedder_dir), device="cpu")
        reranker_model = CrossEncoder(str(reranker_dir), device="cpu")

        self.embedder = SentenceTransformerEmbedder(embedder_model)
        self.reranker = CrossEncoderReranker(reranker_model)
        logger.info("Models loaded from local copies.")
        
        
    def copy_active_models_to_local_runtime_and_load(self, db: Session):
        settings_repo = SettingRepository(db)
        setting = settings_repo.get_current()

        # First-time initialization and safety check
        if not setting or not setting.embedder or not setting.reranker or not Path(setting.embedder.path).exists() or not Path(setting.reranker.path).exists():
            logger.info("Model paths missing or not configured. Attempting to fresh download and save.")
            if not self._download_and_save(db):
                raise RuntimeError("Failed to initialize models. Check logs for details.")
            
            # Refresh the setting object after a successful download
            setting = settings_repo.get_current()

        try:
            active_embedder_path = Path(setting.embedder.path)
            active_reranker_path = Path(setting.reranker.path)
            
            runtime_active_embedder_path = self.config.runtime_model_path / "active_embedder"
            runtime_active_reranker_path = self.config.runtime_model_path / "active_reranker"
            
            copy_dir(active_embedder_path, runtime_active_embedder_path)
            copy_dir(active_reranker_path, runtime_active_reranker_path)
            
            self.load_models_from_path(runtime_active_embedder_path, runtime_active_reranker_path)
            
            logger.info("Models successfully loaded from local copies.")
        
        except Exception as e:
            logger.error(f"An error occurred during model copying or loading: {e}")
            raise RuntimeError("Failed to copy or load models into runtime.") from e
                
        
    
    def _download_and_save(self, db: Session) -> bool:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        
        try:
            model_embedder = SentenceTransformer(self.config.BASE_MODEL_NAME)
            model_reranker = CrossEncoder(self.config.BASE_RERANKER_MODEL_NAME)

            if not (model_embedder and model_reranker):
                logger.error("Failed to download models.")
                return False

            self.config.model_path.mkdir(parents=True, exist_ok=True)

            embedder_path = self.config.model_path / "base_embedder"
            reranker_path = self.config.model_path / "base_reranker"

            model_embedder.save(str(embedder_path))
            model_reranker.save(str(reranker_path))

            # Persist to DB using repositories
            settings_repo = SettingRepository(db)
            embed_repo = EmbedderRepository(db)
            rer_repo = RerankerRepository(db)

            existing_setting = settings_repo.get_current()

            embedder_path_str = str(embedder_path)
            reranker_path_str = str(reranker_path)

            if existing_setting:
                embedder_entry = existing_setting.embedder
                reranker_entry = existing_setting.reranker

                if not embedder_entry:
                    embedder_entry = embed_repo.create(name=self.config.BASE_MODEL_NAME, version="1.0", path=embedder_path_str, is_active=True)
                    db.flush()
                    existing_setting.active_embedder_id = embedder_entry.id
                
                if not reranker_entry:
                    reranker_entry = rer_repo.create(name=self.config.BASE_RERANKER_MODEL_NAME, version="1.0", path=reranker_path_str, normalize_method="default", is_active=True)
                    db.flush()
                    existing_setting.active_reranker_id = reranker_entry.id
                
                # Update paths in case they were downloaded to a new location
                embedder_entry.path = embedder_path_str
                reranker_entry.path = reranker_path_str

                db.add(embedder_entry)
                db.add(reranker_entry)
                db.add(existing_setting)
                db.commit()
                
                logger.info("Existing Setting updated with new model paths.")
            else:
                embedder_entry = embed_repo.create(name=self.config.BASE_MODEL_NAME, version="1.0", path=embedder_path_str, is_active=True)
                reranker_entry = rer_repo.create(name=self.config.BASE_RERANKER_MODEL_NAME, version="1.0", path=reranker_path_str, normalize_method="softmax", is_active=True)
                db.flush()
                new_setting = Setting(active_embedder_id=embedder_entry.id, active_reranker_id=reranker_entry.id)
                db.add(new_setting)
                db.commit()
                
                logger.info("Created new Embedder/Reranker and Setting rows.")

            return True
        except SQLAlchemyError as e:
            try:
                db.rollback()
            except Exception:
                pass
            logger.error(f"Error updating DB: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during download/save: {e}")
            return False
