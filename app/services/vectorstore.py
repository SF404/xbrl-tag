from typing import List, Tuple, Dict, Any
import logging
from langchain.schema import Document
from langchain_community.vectorstores import FAISS

from app.core.config import get_config
from app.core.errors import AppException, ErrorCode
from app.managers.index_cache_manager import index_cache
from app.services.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

class VectorstoreService:
    def __init__(self):
        self.config = get_config()
        self._embed_dim = None

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
        if self._embed_dim is None:
            q_vec = embedder.embed_query("test")
            if q_vec is None:
                raise AppException(
                    ErrorCode.MODEL_NOT_LOADED,
                    "Embedder returned None for query embedding.",
                    status_code=500
                )
            self._embed_dim = len(q_vec)

        if vectorstore.index.d != self._embed_dim:
            logger.warning(
                "Embedding dimension mismatch; rebuild required",
                extra={"index_dim": vectorstore.index.d, "embedder_dim": self._embed_dim},
            )
            raise AppException(
                ErrorCode.DIMENSION_MISMATCH,
                f"Index dim ({vectorstore.index.d}) != embedder dim ({self._embed_dim}). "
                f"Rebuild the index with the active embedder.",
                status_code=409,
            )

    def _perform_similarity_search(self, vectorstore: FAISS, query: str, k: int):
        return vectorstore.similarity_search_with_score(query, k=k)

    def _format_search_results(self, docs_with_scores: List[Tuple[Document, float]], use_rerank_score: bool = False):
        results = []
        for i, (doc, score) in enumerate(docs_with_scores):
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

    def _apply_reranking(self, query: str, docs_with_scores: List[Tuple[Document, float]], reranker, top_k: int):
        docs_only = [doc for doc, _ in docs_with_scores]
        reranked = reranker.rerank(query, docs_only, top_k=top_k)
        return reranked

    def query(self, req, registry) -> Tuple[str, str, List[Dict[str, Any]]]:
        logger.info("Vector query", extra={"taxonomy": req.taxonomy, "k": req.k, "rerank": req.rerank})
        try:
            vectorstore = self.load_index(req.taxonomy, registry.embedder)
        except Exception as e:
            if isinstance(e, AppException):
                logger.error("Failed to load index", extra={"taxonomy": req.taxonomy}, exc_info=True)
                raise
            logger.error("Unexpected error loading index", extra={"taxonomy": req.taxonomy}, exc_info=True)
            raise AppException(
                ErrorCode.INDEX_NOT_FOUND,
                f"Failed to load index for taxonomy '{req.taxonomy}': {str(e)}",
                status_code=404,
            )

        self._validate_embedding_compatibility(vectorstore, registry.embedder)
        k_search = max(req.k * 5, req.k) if req.rerank else req.k
        docs_with_scores = self._perform_similarity_search(vectorstore, req.query, k_search)

        if req.rerank:
            reranked_results = self._apply_reranking(req.query, docs_with_scores, registry.reranker, req.k)
            results = self._format_search_results(reranked_results, use_rerank_score=True)
        else:
            limited_results = docs_with_scores[:req.k]
            results = self._format_search_results(limited_results, use_rerank_score=False)

        logger.info("Vector query completed", extra={"taxonomy": req.taxonomy, "returned": len(results)})
        return req.query, req.taxonomy, results

    def warm_taxonomy(self, taxonomy: str, registry: ModelRegistry) -> None:
        # force load taxonomy
        vs = index_cache.load(taxonomy, registry.embedder, force_reload=True)
        
        # Ensure first encode path is hot
        _ = registry.embedder.embed_query("warmup")
        
        # Touch FAISS
        _ = vs.similarity_search_with_score("warmup", k=1)
        
        # Touch reranker if present
        if registry.reranker:
            dummy = [Document(page_content="", metadata={"reference": "warmup-ref"})]
            _ = registry.reranker.rerank("warmup", dummy, top_k=1)

    def warm_all_disk_indices(self, registry: ModelRegistry):
        taxes = index_cache.disk_indices
        for tax in taxes:
            try:
                self.warm_taxonomy(tax, registry)
            except Exception as e:
                logger.warning("Warmup skipped for taxonomy", extra={"taxonomy": tax, "error": str(e)})
