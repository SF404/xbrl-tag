from typing import List, Tuple, Dict, Any
from langchain.schema import Document
from langchain_community.vectorstores import FAISS

from app.core.config import get_config
from app.core.errors import AppException, ErrorCode
from app.core.index_cache import index_cache


class VectorstoreService:    
    def __init__(self):
        self.config = get_config()
        
    
    def load_index(self, taxonomy: str, embeddings) -> FAISS:
        vectorstore = index_cache.get(taxonomy, embeddings)
        
        if not vectorstore:
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"FAISS index for taxonomy '{taxonomy}' was not found.",
                status_code=404,
            )
        
        return vectorstore
    
    
    def _validate_embedding_compatibility(self, vectorstore: FAISS, embedder) -> None:
        q_vec = embedder.embed_query("test")
        
        if q_vec is None:
            raise AppException(
                ErrorCode.MODEL_NOT_LOADED, 
                "Embedder returned None for query embedding.", 
                status_code=500
            )
        
        if vectorstore.index.d != len(q_vec):
            raise AppException(
                ErrorCode.DIMENSION_MISMATCH,
                f"Index dim ({vectorstore.index.d}) != embedder dim ({len(q_vec)}). "
                f"Rebuild the index with the active embedder.",
                status_code=409,
            )
            
    
    def _perform_similarity_search(self, vectorstore: FAISS, query: str, k: int) -> List[Tuple[Document, float]]:
        return vectorstore.similarity_search_with_score(query, k=k)
    
    
    def _format_search_results(self, docs_with_scores: List[Tuple[Document, float]], 
                             use_rerank_score: bool = False) -> List[Dict[str, Any]]:
        results = []
        for i, (doc, score) in enumerate(docs_with_scores):
            # Convert FAISS distance to similarity score if not reranked
            formatted_score = float(score) if use_rerank_score else float(1 / (1 + score))
            
            result = {
                "tag": doc.metadata["tag"],
                "datatype": doc.metadata["datatype"],
                "reference": doc.metadata["reference"],
                "score": formatted_score,
                "rank": i + 1,
            }
            results.append(result)
        
        return results
    
    def _apply_reranking(self, query: str, docs_with_scores: List[Tuple[Document, float]], 
                        reranker, top_k: int) -> List[Tuple[Document, float]]:
        """Apply reranking to search results"""
        docs_only = [doc for doc, _ in docs_with_scores]
        reranked = reranker.rerank(query, docs_only, top_k=top_k)
        return reranked
    
    def query(self, req, registry) -> Tuple[str, str, List[Dict[str, Any]]]:
        # Load vectorstore
        try:
            vectorstore = self.load_index(req.taxonomy, registry.embedder)
        except Exception as e:
            if isinstance(e, AppException):
                raise
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"Failed to load index for taxonomy '{req.taxonomy}': {str(e)}",
                status_code=404,
            )
        
        # Validate embedding compatibility
        self._validate_embedding_compatibility(vectorstore, registry.embedder)
        
        # Determine search parameters
        k_search = max(req.k * 5, req.k) if req.rerank else req.k
        
        # Perform similarity search
        docs_with_scores = self._perform_similarity_search(vectorstore, req.query, k_search)
        
        # Apply reranking if requested
        if req.rerank:
            reranked_results = self._apply_reranking(
                req.query, docs_with_scores, registry.reranker, req.k
            )
            results = self._format_search_results(reranked_results, use_rerank_score=True)
        else:
            # Limit to requested k for non-reranked results
            limited_results = docs_with_scores[:req.k]
            results = self._format_search_results(limited_results, use_rerank_score=False)
        
        return req.query, req.taxonomy, results


# Global service instance
vectorstore_service = VectorstoreService()
