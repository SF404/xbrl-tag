from fastapi import APIRouter, Depends

from app.core.deps import get_registry, get_vectorstore_service
from app.core.errors import AppException, ErrorCode
from app.schemas.schemas import QueryRequest, QueryResponse, QueryResult
from app.services import ModelRegistry, VectorstoreService

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    registry: ModelRegistry = Depends(get_registry),
    vectorstore: VectorstoreService = Depends(get_vectorstore_service),
):
    """
    Performs a semantic search query against a specified taxonomy.

    This endpoint takes a user's query, uses the active embedder to generate
    a vector, and searches the taxonomy's vector index. It can optionally
    rerank the results using the active reranker model.
    """
    # Ensure the main embedding model is loaded and available.
    if not registry.embedder:
        raise AppException(
            ErrorCode.MODEL_NOT_LOADED,
            "The active embedder model is not loaded.",
            status_code=500,
        )

    # Delegate the query logic to the vectorstore service.
    query_text, taxonomy_name, search_results = vectorstore.query(req, registry)

    # Format the results into the response model.
    formatted_results = [QueryResult(**r) for r in search_results]

    return QueryResponse(
        query=query_text,
        taxonomy=taxonomy_name,
        results=formatted_results,
    )
