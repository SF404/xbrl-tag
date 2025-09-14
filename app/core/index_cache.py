import os
import shutil
from typing import List, Dict, Optional, Any
from pathlib import Path
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from app.core.config import get_config
from app.core.errors import AppException, ErrorCode


class IndexCache:    
    def __init__(self):
        self._cache: Dict[str, FAISS] = {}
        self._config = get_config()
        
    
    @property
    def cache_keys(self) -> List[str]:
        """Get all cached index keys"""
        return list(self._cache.keys())
    
    
    @property
    def disk_indices(self) -> List[str]:
        """Get all index names stored on disk"""
        index_dir = Path(self._config.index_path)
        if not index_dir.exists():
            return []
        return [d.name for d in index_dir.iterdir() if d.is_dir()]
    
    
    def get(self, taxonomy: str, embeddings=None) -> Optional[FAISS]:
        """Get index from cache, load from disk if not cached"""
        # Return from memory cache if available
        if taxonomy in self._cache:
            return self._cache[taxonomy]
        
        # Try to load from disk
        if embeddings and self.exists_on_disk(taxonomy):
            try:
                return self.load(taxonomy, embeddings)
            except Exception as e:
                print(f"Failed to load index {taxonomy} from disk: {e}")
        
        return None
    
    
    def set(self, taxonomy: str, index: FAISS) -> None:
        """Add or update index in cache"""
        self._cache[taxonomy] = index
    
    
    def load(self, taxonomy: str, embeddings, force_reload: bool = False) -> FAISS:
        """Load index from disk into cache"""
        if not force_reload and taxonomy in self._cache:
            return self._cache[taxonomy]
        
        index_path = Path(self._config.index_path) / taxonomy
        if not index_path.exists():
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"Index directory not found: {index_path}",
                status_code=404
            )
        
        try:
            vs = FAISS.load_local(
                str(index_path), 
                embeddings, 
                allow_dangerous_deserialization=True
            )
            self._cache[taxonomy] = vs
            return vs
        except Exception as e:
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"Failed to load FAISS index for '{taxonomy}': {str(e)}",
                status_code=404
            )
    
    
    def save(self, taxonomy: str, index: Optional[FAISS] = None) -> None:
        """Save index to disk"""
        target_index = index or self._cache.get(taxonomy)
        if not target_index:
            raise ValueError(f"No index found for taxonomy: {taxonomy}")
        
        index_path = Path(self._config.index_path) / taxonomy
        index_path.mkdir(parents=True, exist_ok=True)
        target_index.save_local(str(index_path))
    
    
    def remove(self, taxonomy: str, from_disk: bool = False) -> bool:
        """Remove index from cache and optionally from disk"""
        removed = False
        
        # Remove from memory cache
        if taxonomy in self._cache:
            del self._cache[taxonomy]
            removed = True
        
        # Remove from disk if requested
        if from_disk:
            index_path = Path(self._config.index_path) / taxonomy
            if index_path.exists():
                shutil.rmtree(index_path)
                removed = True
        
        return removed
    
    
    def clear(self, from_disk: bool = False) -> None:
        """Clear all indices from cache and optionally from disk"""
        self._cache.clear()
        
        if from_disk:
            index_dir = Path(self._config.index_path)
            if index_dir.exists():
                shutil.rmtree(index_dir)
                index_dir.mkdir(parents=True, exist_ok=True)
    
    
    def exists_in_cache(self, taxonomy: str) -> bool:
        """Check if index exists in memory cache"""
        return taxonomy in self._cache
    
    
    def exists_on_disk(self, taxonomy: str) -> bool:
        """Check if index exists on disk"""
        index_path = Path(self._config.index_path) / taxonomy
        return index_path.exists() and (index_path / "index.faiss").exists()
    
    
    def exists(self, taxonomy: str) -> bool:
        """Check if index exists in cache or on disk"""
        return self.exists_in_cache(taxonomy) or self.exists_on_disk(taxonomy)
    
    
    def update(self, taxonomy: str, new_docs: List[Document], embeddings) -> FAISS:
        """Update existing index with new documents"""
        existing_index = self.get(taxonomy, embeddings)
        if not existing_index:
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"No existing index found for taxonomy: {taxonomy}",
                status_code=404
            )
        
        # Generate embeddings for new docs
        texts = [d.page_content for d in new_docs]
        metas = [d.metadata for d in new_docs]
        vectors = [embeddings.embed_documents([text])[0] for text in texts]
        
        # Create new index from new documents
        new_index = FAISS.from_embeddings(
            text_embeddings=list(zip(texts, vectors)),
            embedding=embeddings,
            metadatas=metas,
        )
        
        # Merge with existing index
        existing_index.merge_from(new_index)
        
        # Update cache and save
        self._cache[taxonomy] = existing_index
        self.save(taxonomy)
        
        return existing_index
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_indices": len(self._cache),
            "disk_indices": len(self.disk_indices),
            "cache_keys": self.cache_keys,
            "disk_keys": self.disk_indices,
            "index_path": self._config.index_path
        }


index_cache = IndexCache()