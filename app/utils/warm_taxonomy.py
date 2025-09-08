from langchain.schema import Document
from app.services.model_registry import ModelRegistry
from app.core.index_cache import index_cache


def warm_taxonomy(taxonomy: str, registry: ModelRegistry) -> None:
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