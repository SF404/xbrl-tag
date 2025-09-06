from typing import List, Tuple
from langchain.schema import Document
from langchain_community.vectorstores import FAISS

from app.core.config import get_config
from app.core.errors import AppException, ErrorCode


# _index_cache: dict = {}

def load_index(taxonomy: str, embeddings) -> FAISS:
    # if taxonomy in _index_cache:
    #     return _index_cache[taxonomy]

    config = get_config()
    index_path = f"{config.index_path}/{taxonomy}"
    vs = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    # _index_cache[taxonomy] = vs
    return vs


def query_vectorstore(req, registry) -> Tuple[str, str, List]:
    try:
        vectorstore = load_index(req.taxonomy, registry.embedder)
    except Exception:
        raise AppException(
            ErrorCode.INDEX_NOT_FOUND,
            f"FAISS index for taxonomy '{req.taxonomy}' was not found.",
            status_code=404,
        )

    # Guard against dimension mismatch
    q_vec = registry.embedder.embed_query(req.query)
    if q_vec is None:
        raise AppException(ErrorCode.MODEL_NOT_LOADED, "Embedder returned None for query embedding.", status_code=500)

    if vectorstore.index.d != len(q_vec):
        raise AppException(
            ErrorCode.DIMENSION_MISMATCH,
            f"Index dim ({vectorstore.index.d}) != embedder dim ({len(q_vec)}). Rebuild the index with the active embedder.",
            status_code=409,
        )

    # Similarity search (retrieve more if reranking)
    docs_with_scores: List[Tuple[Document, float]] = vectorstore.similarity_search_with_score(req.query, k=max(req.k * 5, req.k))

    if req.rerank:
        docs_only = [doc for doc, _ in docs_with_scores]
        reranked = registry.reranker.rerank(req.query, docs_only, top_k=req.k)
        results = [
            {
                "tag": d.metadata["tag"],
                "datatype": d.metadata["datatype"],
                "reference": d.metadata["reference"],
                "score": float(score),
                "rank": i + 1,
            }
            for i, (d, score) in enumerate(reranked)
        ]
    else:
        results = [
            {
                "tag": doc.metadata["tag"],
                "datatype": doc.metadata["datatype"],
                "reference": doc.metadata["reference"],
                "score": float(1 / (1 + score)),
                "rank": i + 1,
            }
            for i, (doc, score) in enumerate(docs_with_scores[:req.k])
        ]

    return req.query, req.taxonomy, results
