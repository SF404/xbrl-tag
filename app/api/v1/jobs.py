import uuid
from fastapi import APIRouter, BackgroundTasks, Depends
from langchain.schema import Document
from sqlalchemy.orm import Session

from app.core.errors import AppException, ErrorCode
from app.schemas.query import BuildRequest
from app.core.deps import get_registry, get_db
from app.services.data_service import get_taxonomy_by_taxonomy_name
from app.services.job_service import build_index_async
from app.jobs.manager import job_get, job_all


router = APIRouter()


@router.post("/build_index")
def build_index(req: BuildRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), registry=Depends(get_registry)):
    taxonomy = get_taxonomy_by_taxonomy_name(db, req.taxonomy)
    if not taxonomy:
        raise AppException(ErrorCode.NOT_FOUND, f"Taxonomy with symbol '{req.taxonomy}' not found.", status_code=404)

    docs = [
        Document(
            page_content=entry.reference,
            metadata={"tag": entry.tag, "datatype": entry.datatype, "reference": entry.reference},
        )
        for entry in taxonomy.entries
    ]
    job_id = str(uuid.uuid4())
    background_tasks.add_task(build_index_async, job_id, docs, registry.embedder, req.taxonomy)
    return {"message": "Index build started", "job_id": job_id}


@router.get("/status/all")
def get_jobs():
    return job_all()

@router.get("/status/{job_id}")
def get_status(job_id: str):
    return job_get(job_id, {"error": "Job not found"})
