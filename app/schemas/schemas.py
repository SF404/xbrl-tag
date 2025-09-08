from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime, date

# -------- System
class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    backend: str
    database_status: str

# -------- Query
class QueryRequest(BaseModel):
    query: str
    taxonomy: str
    k: int = Field(5, gt=0, le=100)
    rerank: bool = True

class QueryResult(BaseModel):
    tag: str
    datatype: str
    reference: str
    score: float
    rank: int

class QueryResponse(BaseModel):
    query: str
    taxonomy: str
    results: List[QueryResult]

# -------- Jobs / Index
class BuildIndexRequest(BaseModel):
    taxonomy: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    total: int
    done: int
    taxonomy: Optional[str]
    error: Optional[str]

class JobsListResponse(BaseModel):
    jobs: Dict[str, JobStatusResponse]

class CacheStatsResponse(BaseModel):
    cached_indices: int
    disk_indices: int
    cache_keys: List[str]
    disk_keys: List[str]
    index_path: str

# -------- Models
class EmbedderResponse(BaseModel):
    id: int
    name: str
    version: str
    path: str
    is_active: bool
    class Config:
        from_attributes = True

class RerankerResponse(BaseModel):
    id: int
    name: str
    version: str
    path: str
    normalize_method: str
    is_active: bool
    class Config:
        from_attributes = True

class ActiveModelsResponse(BaseModel):
    active_embedder: Optional[EmbedderResponse]
    active_reranker: Optional[RerankerResponse]

class UpdateSettingsRequest(BaseModel):
    active_embedder_id: Optional[int] = None
    active_reranker_id: Optional[int] = None

# -------- Taxonomy
class TaxonomyResponse(BaseModel):
    id: int
    sheet_name: str
    taxonomy: str
    description: Optional[str]
    source_file: Optional[str]
    class Config:
        from_attributes = True

class TaxonomyEntryResponse(BaseModel):
    id: int
    taxonomy_id: int
    tag: str
    datatype: str
    reference: str
    class Config:
        from_attributes = True

class AddEntryRequest(BaseModel):
    taxonomy_id: int
    tag: str
    datatype: str
    reference: str

class UpdateEntryRequest(BaseModel):
    tag: Optional[str] = None
    datatype: Optional[str] = None
    reference: Optional[str] = None
    
class UploadTaxonomyRequest(BaseModel):
    taxonomy: str
    description: str
    sheet_name: str

class UploadTaxonomyResponse(BaseModel):
    taxonomy_id: int

# -------- Feedback
class FeedbackResponse(BaseModel):
    id: int
    taxonomy_id: int
    query: str
    reference: Optional[str]
    tag: str
    is_correct: bool
    is_custom: bool
    rank: Optional[int]
    created_at: datetime
    class Config:
        from_attributes = True

class FeedbackCreateRequest(BaseModel):
    taxonomy: str
    query: str
    reference: Optional[str] = None
    tag: str
    is_correct: bool
    is_custom: bool = False
    rank: Optional[int] = None

class FeedbackUpdateRequest(BaseModel):
    id: int
    query: Optional[str] = None
    reference: Optional[str] = None
    tag: Optional[str] = None
    is_correct: Optional[bool] = None
    is_custom: Optional[bool] = None
    rank: Optional[int] = None
    
class FeedbackListQuery(BaseModel):
    taxonomy: Optional[str] = None
    date_from: Optional[date] = Field(None, description="YYYY-MM-DD")
    date_to: Optional[date] = Field(None, description="YYYY-MM-DD")
    offset: int = Field(0, ge=0)
    limit: int = Field(200, ge=1, le=2000)

# -------- Misc
class MessageResponse(BaseModel):
    message: str
