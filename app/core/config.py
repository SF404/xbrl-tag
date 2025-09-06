from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Config(BaseSettings):
    # model_config = SettingsConfigDict(
    #     env_file=".env", 
    #     env_file_encoding="utf-8"
    # )

    APP_NAME: str = Field("XBRL Tag Recommender API", env="APP_NAME")
    APP_VERSION: str = Field("0.1.0", env="APP_VERSION")
    APP_ENV: str = Field("development", env="APP_ENV") # or production
    API_PREFIX: str = Field("/api/v1", env="API_PREFIX")
    DEBUG: bool = Field(True, env="DEBUG")

    DEVICE: str = Field("cpu", env="DEVICE") # or cuda -> dont use gpu for now

    # Database settings
    DB_USER: str = Field(..., env="DB_USER")
    DB_PASSWORD: str = Field(..., env="DB_PASSWORD")
    DB_HOST: str = Field(..., env="DB_HOST")
    DB_PORT: int = Field(5432, env="DB_PORT")
    DB_NAME: str = Field(..., env="DB_NAME")

    # GCP storage settings
    GCP_PROJECT_ID: str = Field(..., env="GCP_PROJECT_ID")
    GCP_BUCKET_NAME: str = Field(..., env="GCP_BUCKET_NAME")
    GCP_BUCKET_PREFIX: str = Field(..., env="GCP_BUCKET_PREFIX")
    GCP_CREDENTIALS_PATH: str | None = None

    GCP_INDEX_PATH: str = Field(..., env="GCP_INDEX_PATH")
    GCP_MODEL_PATH: str = Field(..., env="GCP_MODEL_PATH")

    # Local storage settings
    LOCAL_STORAGE_PATH: str = Field(..., env="LOCAL_STORAGE_PATH")
    LOCAL_INDEX_PATH: str = Field(..., env="LOCAL_INDEX_PATH")
    LOCAL_MODEL_PATH: str = Field(..., env="LOCAL_MODEL_PATH")

    # base model
    BASE_MODEL_NAME: str = Field(..., env="BASE_MODEL_NAME")
    BASE_RERANKER_MODEL_NAME: str = Field(..., env="BASE_RERANKER_MODEL_NAME")

    # misc
    ALLOW_ORIGINS: list[str] = Field([
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
    def backend(self) -> str:
        return "local" if self.is_development else "gcp"
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
@lru_cache
def get_config() -> Config:
    return Config()




    



