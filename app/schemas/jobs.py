from pydantic import BaseModel
from typing import List

class CacheStatsResponse(BaseModel):
    cached_indices: int
    disk_indices: int
    cache_keys: List[str]
    disk_keys: List[str]
    index_path: str
    
