from fastapi import APIRouter, Depends

from app.core.deps import get_registry, get_vectorstore_service
from app.core.errors import AppException, ErrorCode
from app.schemas.schemas import QueryRequest, QueryResponse, QueryResult

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    registry = Depends(get_registry),
    vectorstore = Depends(get_vectorstore_service),
):
    if not registry.embedder:
        raise AppException(ErrorCode.MODEL_NOT_LOADED, "Active embedder not loaded", status_code=500)
    q, tax, results = vectorstore.query(req, registry)
    return QueryResponse(query=q, taxonomy=tax, results=[QueryResult(**r) for r in results])