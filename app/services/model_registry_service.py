import os
import tempfile
import shutil
import json
import hashlib
from pathlib import Path
from google.cloud import storage
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_config
from app.models.entities import Setting, Embedder, Reranker
from app.services.model_download_service import ModelDownloadService
from app.services.gcp_upload_service import ModelUploadService
from app.db.session import SessionLocal


class ModelRegistry:
    def __init__(self):
        self.config = get_config()
        self.embedder = None
        self.reranker = None

    # -------------------------
    # Public entry
    # -------------------------
    def load_models(self, db: Session):
        settings = db.query(Setting).first()

        if settings and settings.embedder and settings.reranker:
            print("[ModelRegistry] Found existing models in DB, validating paths...")

            embedder_path = settings.embedder.path
            reranker_path = settings.reranker.path

            # Local backend → check filesystem
            if self.config.backend == "local":
                if self._load_models_from_local_paths(embedder_path, reranker_path):
                    print("[ModelRegistry] Models loaded from local filesystem.")
                    return
                else:
                    print("[ModelRegistry] Local paths missing or invalid. Re-downloading models...")

            # GCP backend → check bucket (use persistent local cache)
            elif self.config.backend == "gcp":
                self._load_models_from_gcp_cache(db, embedder_path, reranker_path)
                return

            # Fallback: Re-download and re-save
            self._download_and_save()
            return

        # No settings → first-time setup
        print("[ModelRegistry] No settings in DB. Fresh download...")
        self._download_and_save()

    # -------------------------
    # Original download + DB save (unchanged)
    # -------------------------
    def _download_and_save(self):
        """Download from HF → save locally/GCP → update DB"""
        model_download_service = ModelDownloadService()
        model_embedder = model_download_service.download_embedder(self.config.BASE_MODEL_NAME)
        model_reranker = model_download_service.download_reranker(self.config.BASE_RERANKER_MODEL_NAME)

        if not (model_embedder and model_reranker):
            raise RuntimeError("[ModelRegistry] Failed to download models.")

        self.embedder = model_embedder
        self.reranker = model_reranker

        if self.config.backend == "local":
            os.makedirs(self.config.LOCAL_MODEL_PATH, exist_ok=True)
            embedder_path = os.path.join(self.config.LOCAL_MODEL_PATH, "base_embedder")
            reranker_path = os.path.join(self.config.LOCAL_MODEL_PATH, "base_reranker")
            model_embedder.save(embedder_path)
            model_reranker.save(reranker_path)

        elif self.config.backend == "gcp":
            with tempfile.TemporaryDirectory() as tmp_dir:
                embedder_dir = os.path.join(tmp_dir, "base_embedder")
                reranker_dir = os.path.join(tmp_dir, "base_reranker")
                model_embedder.save(embedder_dir)
                model_reranker.save(reranker_dir)

                # Zip directories
                embedder_zip = shutil.make_archive(embedder_dir, 'zip', embedder_dir)
                reranker_zip = shutil.make_archive(reranker_dir, 'zip', reranker_dir)

                upload_service = ModelUploadService()
                print("[ModelRegistry] Uploading base_embedder to GCP...")
                upload_service.upload_file(embedder_zip, f"{self.config.GCP_BUCKET_PREFIX}/base_embedder.zip")
                print("[ModelRegistry] Uploading base_reranker to GCP...")
                upload_service.upload_file(reranker_zip, f"{self.config.GCP_BUCKET_PREFIX}/base_reranker.zip")

                embedder_path = f"gs://{self.config.GCP_BUCKET_NAME}/{self.config.GCP_BUCKET_PREFIX}/base_embedder.zip"
                reranker_path = f"gs://{self.config.GCP_BUCKET_NAME}/{self.config.GCP_BUCKET_PREFIX}/base_reranker.zip"

        # Update DB with new paths
        try:
            with SessionLocal() as db:
                existing_setting = db.query(Setting).first()

                if existing_setting:
                    embedder_entry = db.get(Embedder, existing_setting.active_embedder_id)
                    reranker_entry = db.get(Reranker, existing_setting.active_reranker_id)

                    embedder_entry.path = embedder_path
                    reranker_entry.path = reranker_path

                    db.add(embedder_entry)
                    db.add(reranker_entry)
                    db.commit()
                    print("[ModelRegistry] Existing Setting updated with new model paths.")
                else:
                    embedder_entry = Embedder(
                        name=self.config.BASE_MODEL_NAME,
                        version="1.0",
                        path=embedder_path,
                        is_active=True
                    )
                    reranker_entry = Reranker(
                        name=self.config.BASE_RERANKER_MODEL_NAME,
                        version="1.0",
                        path=reranker_path,
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

    # -------------------------
    # GCP cache loader (modular)
    # -------------------------
    def _load_models_from_gcp_cache(self, db: Session, embedder_path: str, reranker_path: str):
        """
        Driver for GCP persistent caching + loading.
        """
        base_cache_dir = self._get_cache_dir()
        index_file = base_cache_dir / "cache_index.json"

        # Fingerprint of current DB active-model paths
        settings_fingerprint = hashlib.sha256(
            (str(embedder_path) + "::" + str(reranker_path)).encode("utf-8")
        ).hexdigest()

        # Derive blob names
        embedder_blob_name = self._blob_name_from_gs_path(embedder_path)
        reranker_blob_name = self._blob_name_from_gs_path(reranker_path)

        # Read index (if exists)
        index = self._read_index(index_file)

        # Check cache validity
        cache_valid = False
        local_embedder_dir = None
        local_reranker_dir = None
        if index:
            if (
                index.get("fingerprint") == settings_fingerprint
                and index.get("embedder_remote") == embedder_blob_name
                and index.get("reranker_remote") == reranker_blob_name
            ):
                local_embedder_dir = base_cache_dir / index.get("embedder_local", "")
                local_reranker_dir = base_cache_dir / index.get("reranker_local", "")
                if local_embedder_dir.exists() and local_reranker_dir.exists():
                    cache_valid = True

        # Fast load from cache if valid
        if cache_valid:
            if self._load_models_from_dirs(local_embedder_dir, local_reranker_dir):
                print("[ModelRegistry] Models loaded from persistent local cache.")
                return
            else:
                print("[ModelRegistry] Failed to load from cache (will re-download).")
                cache_valid = False

        # Setup GCS client and blobs
        client, bucket = self._init_gcs_client()
        embedder_blob = bucket.blob(embedder_blob_name)
        reranker_blob = bucket.blob(reranker_blob_name)

        # Ensure blobs exist in GCS
        if not (embedder_blob.exists() and reranker_blob.exists()):
            print("[ModelRegistry] GCP blobs missing for the current active models. Falling back to re-download via _download_and_save().")
            self._download_and_save()
            return

        # Create stable local target dirs (based on blob names)
        embedder_dirname = f"embedder_{self._safe_dir_name(embedder_blob_name)}"
        reranker_dirname = f"reranker_{self._safe_dir_name(reranker_blob_name)}"
        local_embedder_dir = base_cache_dir / embedder_dirname
        local_reranker_dir = base_cache_dir / reranker_dirname

        # Invalidate previous cache if fingerprint changed
        if index.get("fingerprint") and index.get("fingerprint") != settings_fingerprint:
            self._invalidate_old_cache(base_cache_dir, index, local_embedder_dir, local_reranker_dir)

        # Download blobs and unpack (atomic-ish)
        try:
            self._download_and_unpack_blob(embedder_blob, local_embedder_dir, embedder_dirname, base_cache_dir)
            self._download_and_unpack_blob(reranker_blob, local_reranker_dir, reranker_dirname, base_cache_dir)

            # Update index atomically
            new_index = {
                "fingerprint": settings_fingerprint,
                "embedder_remote": embedder_blob_name,
                "reranker_remote": reranker_blob_name,
                "embedder_local": embedder_dirname,
                "reranker_local": reranker_dirname,
            }
            self._write_index_atomic(index_file, new_index)

            # Load models from cached dirs
            if self._load_models_from_dirs(local_embedder_dir, local_reranker_dir):
                print("[ModelRegistry] Models downloaded from GCP and cached on local filesystem.")
                return
            else:
                raise RuntimeError("Failed to load models after caching.")

        except Exception as e:
            print(f"[ModelRegistry] Error while caching models from GCP: {e}")
            # Fallback to original download/save logic which also updates DB
            self._download_and_save()
            return

    # -------------------------
    # Helper methods
    # -------------------------
    def _get_cache_dir(self) -> Path:
        """
        Return a persistent cache directory for GCP model cache.
        Using a dedicated hidden folder in user's home to avoid colliding with LOCAL_MODEL_PATH.
        """
        base_cache_dir = Path.home() / ".gcp_model_cache" / "models"
        base_cache_dir.mkdir(parents=True, exist_ok=True)
        return base_cache_dir

    def _read_index(self, index_file: Path) -> dict:
        if not index_file.exists():
            return {}
        try:
            with open(index_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_index_atomic(self, index_file: Path, data: dict):
        tmp_index_file = index_file.with_suffix(".tmp")
        with open(tmp_index_file, "w") as f:
            json.dump(data, f)
        tmp_index_file.replace(index_file)

    def _blob_name_from_gs_path(self, gs_path: str) -> str:
        prefix = f"gs://{self.config.GCP_BUCKET_NAME}/"
        return gs_path.replace(prefix, "").strip("/")

    def _safe_dir_name(self, blob_name: str) -> str:
        return hashlib.sha1(blob_name.encode("utf-8")).hexdigest()

    def _init_gcs_client(self):
        client = storage.Client.from_service_account_json(self.config.GCP_CREDENTIALS_PATH)
        bucket = client.bucket(self.config.GCP_BUCKET_NAME)
        return client, bucket

    def _invalidate_old_cache(self, base_cache_dir: Path, index: dict, target_embed_dir: Path, target_rerank_dir: Path):
        try:
            old_embed = base_cache_dir / index.get("embedder_local", "")
            old_rerank = base_cache_dir / index.get("reranker_local", "")
            if old_embed.exists() and old_embed != target_embed_dir:
                shutil.rmtree(old_embed)
            if old_rerank.exists() and old_rerank != target_rerank_dir:
                shutil.rmtree(old_rerank)
        except Exception as e:
            print(f"[ModelRegistry] Warning removing old cache directories: {e}")

    def _download_and_unpack_blob(self, blob, target_dir: Path, dir_name: str, base_cache_dir: Path):
        """
        Download a blob into base_cache_dir/{dir_name}.zip.tmp, rename to .zip atomically,
        and unpack into target_dir. If target_dir exists it will be removed first.
        """
        tmp_path = base_cache_dir / f"{dir_name}.zip.tmp"
        final_path = base_cache_dir / f"{dir_name}.zip"

        # 1) Download to tmp file
        blob.download_to_filename(str(tmp_path))

        # 2) Atomically replace .zip.tmp -> .zip
        try:
            os.replace(str(tmp_path), str(final_path))
        except Exception:
            # best-effort fallback to rename
            tmp_path.rename(final_path)

        # 3) Clean target dir if present, then unpack
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Use shutil.unpack_archive (requires .zip extension)
        shutil.unpack_archive(str(final_path), str(target_dir))

        # 4) Optionally remove the final .zip to save space
        try:
            final_path.unlink(missing_ok=True)
        except TypeError:
            # For Python versions < 3.8 where missing_ok isn't available
            try:
                final_path.unlink()
            except FileNotFoundError:
                pass

    def _load_models_from_dirs(self, embedder_dir: Path, reranker_dir: Path) -> bool:
        """
        Load models from given directories. Returns True on success, False otherwise.
        """
        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder

            self.embedder = SentenceTransformer(str(embedder_dir), device="cpu")
            self.reranker = CrossEncoder(str(reranker_dir), device="cpu")
            return True
        except Exception as e:
            print(f"[ModelRegistry] Error loading models from dirs: {e}")
            return False

    def _load_models_from_local_paths(self, embedder_path: str, reranker_path: str) -> bool:
        """
        Load models from local paths. Supports:
          - directory paths (directly load)
          - .zip files (unpack to a temporary dir and load)
        Returns True on success, False otherwise.
        """
        embedder_p = Path(embedder_path)
        reranker_p = Path(reranker_path)

        if not (embedder_p.exists() and reranker_p.exists()):
            return False

        temp_dirs = []  # store TemporaryDirectory objects to cleanup later

        try:
            # Prepare embedder directory
            if embedder_p.is_dir():
                local_embedder_dir = embedder_p
            elif embedder_p.suffix.lower() == ".zip":
                tmp_embed = tempfile.TemporaryDirectory()
                shutil.unpack_archive(str(embedder_p), tmp_embed.name)
                local_embedder_dir = Path(tmp_embed.name)
                temp_dirs.append(tmp_embed)
            else:
                # fallback: treat as directory-like path (attempt to load)
                local_embedder_dir = embedder_p

            # Prepare reranker directory
            if reranker_p.is_dir():
                local_reranker_dir = reranker_p
            elif reranker_p.suffix.lower() == ".zip":
                tmp_rerank = tempfile.TemporaryDirectory()
                shutil.unpack_archive(str(reranker_p), tmp_rerank.name)
                local_reranker_dir = Path(tmp_rerank.name)
                temp_dirs.append(tmp_rerank)
            else:
                local_reranker_dir = reranker_p

            # Use the existing loader; it will set self.embedder/self.reranker
            return self._load_models_from_dirs(local_embedder_dir, local_reranker_dir)

        except Exception as e:
            print(f"[ModelRegistry] Error loading local models: {e}")
            return False

        finally:
            # cleanup temp dirs (if any)
            for td in temp_dirs:
                try:
                    td.cleanup()
                except Exception:
                    pass
