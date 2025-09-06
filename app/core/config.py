from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from typing import Optional, List

class Config(BaseSettings): 
    model_config = SettingsConfigDict(
        env_file=".env",          
        env_file_encoding="utf-8"
    )
    APP_NAME: str = Field("XBRL Tag Recommender API", env="APP_NAME")
    APP_VERSION: str = Field("0.1.0", env="APP_VERSION")
    APP_ENV: str = Field("development", env="APP_ENV")
    API_PREFIX: str = Field("/api/v1", env="API_PREFIX")
    DEBUG: bool = Field(True, env="DEBUG")

    DEVICE: str = Field("cpu", env="DEVICE")

    # Database variables
    DB_USER: str = Field(..., env="DB_USER")
    DB_PASSWORD: str = Field(..., env="DB_PASSWORD")
    DB_HOST: str = Field(..., env="DB_HOST")
    DB_PORT: int = Field(5432, env="DB_PORT")
    DB_NAME: str = Field(..., env="DB_NAME")

    # Cloud Storage volume mount path for models (explicit mounted path)
    MOUNTED_STORAGE_PATH: Path = Field(Path("/mnt/data"), env="MOUNTED_STORAGE_PATH")

    INDEX_PATH: Optional[Path] = Field(None, env="INDEX_PATH")
    MODEL_PATH: Optional[Path] = Field(None, env="MODEL_PATH")

    # Base model names for download from Hugging Face
    BASE_MODEL_NAME: str = Field(..., env="BASE_MODEL_NAME")
    BASE_RERANKER_MODEL_NAME: str = Field(..., env="BASE_RERANKER_MODEL_NAME")

    # Misc settings
    ALLOW_ORIGINS: List[str] = Field([
        "http://localhost:3000",
        "http://localhost:5174",
        "http://localhost:8000",
        "https://xbrl.briskbold.ai",
    ], env="ALLOW_ORIGINS")

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def model_path(self) -> Path:
        if self.MODEL_PATH:
            mp = Path(self.MODEL_PATH)
            if str(self.MOUNTED_STORAGE_PATH) not in str(mp):
                return Path(self.MOUNTED_STORAGE_PATH) / mp
            return mp
        return Path(self.MOUNTED_STORAGE_PATH) / "models"

    @property
    def index_path(self) -> Path:
        if self.INDEX_PATH:
            ip = Path(self.INDEX_PATH)
            if str(self.MOUNTED_STORAGE_PATH) not in str(ip):
                return Path(self.MOUNTED_STORAGE_PATH) / ip
            return ip
        return Path(self.MOUNTED_STORAGE_PATH) / "index"


@lru_cache
def get_config() -> Config:
    return Config()
