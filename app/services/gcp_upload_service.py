
from google.cloud import storage
from app.core.config import get_config

class ModelUploadService:
    def __init__(self):
        self.config = get_config()
        self.client = storage.Client.from_service_account_json(
            self.config.GCP_CREDENTIALS_PATH
        )
        self.bucket = self.client.bucket(self.config.GCP_BUCKET_NAME)

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        try:
            blob = self.bucket.blob(remote_path)
            blob.chunk_size = 50 * 1024 * 1024
            blob.upload_from_filename(local_path, timeout=600)
            print(f"[ModelUploadService] Uploaded {local_path} to gs://{self.config.GCP_BUCKET_NAME}/{remote_path}")
            return True
        except Exception as e:
            print(f"[ModelUploadService] Error uploading {local_path}: {e}")
            return False
