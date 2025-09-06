from fastapi import APIRouter, Depends

from app.schemas.query import QueryRequest, QueryResponse, QueryResult
from app.core.deps import get_registry
from app.services.vectorstore_service import query_vectorstore


router = APIRouter()
@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, registry=Depends(get_registry)) -> QueryResponse:
    query_text, taxonomy, raw_results = query_vectorstore(req, registry)
    results = [
        QueryResult(
            tag=r["tag"],
            datatype=r["datatype"],
            reference=r["reference"],
            score=r["score"],
            rank=r["rank"],
        )
        for r in raw_results
    ]

    return QueryResponse(query=query_text, taxonomy=taxonomy, results=results)
