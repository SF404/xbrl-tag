from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_config
from app.models.entities import Setting, Embedder, Reranker
from app.services.model_download_service import ModelDownloadService
from app.db.session import SessionLocal
from langchain.schema import Document
from typing import List, Any, Tuple
import numpy as np

try:
    from langchain.embeddings.base import Embeddings
except Exception:
    from langchain.embeddings import Embeddings

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
    def __init__(self, model: str, normalize_method: str = "softmax"):
        self.model = model
        self.normalize_method = normalize_method

    def rerank(self, query: str, docs: List[Document], top_k: int = 5):
        pairs = [(query, d.metadata["reference"]) for d in docs]
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

    def load_models(self, db: Session):
        settings = db.query(Setting).first()

        if settings and settings.embedder and settings.reranker:
            print("[ModelRegistry] Found existing models in DB, validating paths...")

            embedder_path = settings.embedder.path
            reranker_path = settings.reranker.path
            
            if Path(embedder_path).exists() and Path(reranker_path).exists():
                from sentence_transformers import SentenceTransformer, CrossEncoder
                
                embedder_model = SentenceTransformer(embedder_path, device="cpu")
                reranker_model = CrossEncoder(reranker_path, device="cpu")
                
                self.embedder = SentenceTransformerEmbedder(embedder_model)
                self.reranker = CrossEncoderReranker(reranker_model)
                
                print("[ModelRegistry] Models loaded from local filesystem.")
                return
            else:
                print("[ModelRegistry] Local paths missing. Re-downloading models...")

            # Fallback: Re-download and re-save
            self._download_and_save()
            return

        # No settings → first-time setup
        print("[ModelRegistry] No settings in DB. Fresh download...")
        self._download_and_save()

    def _download_and_save(self):
        # Download model from hugging face and save
        model_download_service = ModelDownloadService()
        model_embedder = model_download_service.download_embedder(self.config.BASE_MODEL_NAME)
        model_reranker = model_download_service.download_reranker(self.config.BASE_RERANKER_MODEL_NAME)

        if not (model_embedder and model_reranker):
            raise RuntimeError("[ModelRegistry] Failed to download models.")

        # Ensure base model path exists (model_path is a Path from your Config)
        self.config.model_path.mkdir(parents=True, exist_ok=True)

        embedder_path = self.config.model_path / "base_embedder"
        reranker_path = self.config.model_path / "base_reranker"

        # Save models (sentence-transformers accepts str or Path; use str for safety)
        model_embedder.save(str(embedder_path))
        model_reranker.save(str(reranker_path))
        
        self.embedder = SentenceTransformerEmbedder(model_embedder)
        self.reranker = CrossEncoderReranker(model_reranker)

        # Update DB with new paths (convert Path -> str before storing)
        try:
            with SessionLocal() as db:
                existing_setting = db.query(Setting).first()

                # Prepare string versions
                embedder_path_str = str(embedder_path)
                reranker_path_str = str(reranker_path)

                if existing_setting:
                    embedder_entry = db.get(Embedder, existing_setting.active_embedder_id)
                    reranker_entry = db.get(Reranker, existing_setting.active_reranker_id)

                    # If entries are missing for some reason, create them
                    if embedder_entry is None:
                        embedder_entry = Embedder(
                            name=self.config.BASE_MODEL_NAME,
                            version="1.0",
                            path=embedder_path_str,
                            is_active=True
                        )
                        db.add(embedder_entry)
                        db.flush()
                        existing_setting.active_embedder_id = embedder_entry.id

                    if reranker_entry is None:
                        reranker_entry = Reranker(
                            name=self.config.BASE_RERANKER_MODEL_NAME,
                            version="1.0",
                            path=reranker_path_str,
                            normalize_method="default",
                            is_active=True
                        )
                        db.add(reranker_entry)
                        db.flush()
                        existing_setting.active_reranker_id = reranker_entry.id

                    # IMPORTANT: assign string values
                    embedder_entry.path = embedder_path_str
                    reranker_entry.path = reranker_path_str

                    db.add(embedder_entry)
                    db.add(reranker_entry)
                    db.add(existing_setting)
                    db.commit()
                    print("[ModelRegistry] Existing Setting updated with new model paths.")
                else:
                    embedder_entry = Embedder(
                        name=self.config.BASE_MODEL_NAME,
                        version="1.0",
                        path=embedder_path_str,
                        is_active=True
                    )
                    reranker_entry = Reranker(
                        name=self.config.BASE_RERANKER_MODEL_NAME,
                        version="1.0",
                        path=reranker_path_str,
                        normalize_method="default",
                        is_active=True
                    )
                    db.add(embedder_entry)
                    db.add(reranker_entry)
                    db.flush()

                    new_setting = Setting(
                        active_embedder_id=embedder_entry.id,
                        active_reranker_id=reranker_entry.id
                    )
                    db.add(new_setting)
                    db.commit()
                    print("[ModelRegistry] Created new Embedder/Reranker and Setting rows.")
        except SQLAlchemyError as e:
            try:
                db.rollback()
            except Exception:
                pass
            print(f"[ModelRegistry] Error updating DB: {e}")
            
            
    def get_active_model_paths(self, db: Session) -> Tuple[str, str]:
        settings = db.query(Setting).first()
        if not settings or not settings.embedder or not settings.reranker:
            raise RuntimeError("[ModelRegistry] Active models are not configured in DB.")
        return settings.embedder.path, settings.reranker.path
    
    
    def load_models_from_local(self, embedder_dir: Path, reranker_dir: Path) -> None:
        from sentence_transformers import SentenceTransformer, CrossEncoder

        embedder_model = SentenceTransformer(str(embedder_dir), device="cpu")
        reranker_model = CrossEncoder(str(reranker_dir), device="cpu")

        self.embedder = SentenceTransformerEmbedder(embedder_model)
        self.reranker = CrossEncoderReranker(reranker_model)
        print("[ModelRegistry] Models loaded from local copies.")

