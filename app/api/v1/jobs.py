import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from app.core.deps import get_registry, get_jobs_manager
from app.core.errors import AppException, ErrorCode
from app.core.index_cache import index_cache
from app.schemas.schemas import CacheStatsResponse, BuildIndexRequest, FineTuneEmbedderRequest, FineTuneRerankerRequest
from app.services import build_index_async, finetune_reranker_async, finetune_embedder_async

router = APIRouter()

@router.post("/build_index")
def build_index(
    req: BuildIndexRequest,
    background_tasks: BackgroundTasks,
    registry = Depends(get_registry),
    jobs = Depends(get_jobs_manager),
):
    if not req.taxonomy:
        raise AppException(ErrorCode.VALIDATION_ERROR, "taxonomy is required", status_code=422)
    if not registry or not registry.embedder:
        raise AppException(ErrorCode.MODEL_NOT_LOADED, "Active embedder not loaded", status_code=500)

    # Prevent duplicate concurrent builds for the same taxonomy
    active = jobs.find_active_for_taxonomy(req.taxonomy)
    if active:
        jid, state = active
        return {"message": "Build already running", "job_id": jid, "status": state["status"]}

    job_id = str(uuid.uuid4())
    jobs.set(job_id, {"status": "queued", "progress": 0, "total": 0, "done": 0, "taxonomy": req.taxonomy})

    background_tasks.add_task(build_index_async, job_id, req.taxonomy, registry, jobs)
    return {"message": "Index build started", "job_id": job_id}

@router.post("/finetune_embedder")
def finetune_embedder(
    background_tasks: BackgroundTasks,
    req: FineTuneEmbedderRequest,
    jobs = Depends(get_jobs_manager),
):
    # Validate the request parameters
    if not req.embedder_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "embedder_id is required", status_code=422)

    job_id = str(uuid.uuid4())
    job_payload = {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "done": 0,
        "embedder_id": req.embedder_id,
        "feedback_date_from": req.date_from,
        "feedback_date_to": req.date_to,
    }

    jobs.set(job_id, job_payload)

    # Add the task to background to perform finetuning
    background_tasks.add_task(finetune_embedder_async, job_id, req.embedder_id, req.date_from, req.date_to, jobs)

    return {"message": "Finetuning for embedder started", "job_id": job_id}

@router.post("/finetune_reranker")
def finetune_reranker(
    background_tasks: BackgroundTasks,
    req: FineTuneRerankerRequest,
    jobs = Depends(get_jobs_manager),
):
    # Validate the request parameters
    if not req.reranker_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "reranker_id is required", status_code=422)

    job_id = str(uuid.uuid4())
    job_payload = {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "done": 0,
        "reranker_id": req.reranker_id,
        "feedback_date_from": req.date_from,
        "feedback_date_to": req.date_to,
    }

    jobs.set(job_id, job_payload)

    background_tasks.add_task(finetune_reranker_async, job_id, req.reranker_id, req.date_from, req.date_to, jobs)

    return {"message": "Finetuning for reranker started", "job_id": job_id}

@router.get("/status/all")
def get_jobs(jobs = Depends(get_jobs_manager)):
    return jobs.all()

@router.get("/status/{job_id}")
def get_status(job_id: str, jobs = Depends(get_jobs_manager)):
    data = jobs.get(job_id)
    if not data:
        return {"error": "Job not found"}
    return data

@router.get("/index_cache/stats", response_model=CacheStatsResponse)
def get_cache_stats():
    try:
        stats = index_cache.get_stats()
        stats["index_path"] = str(stats["index_path"])
        return CacheStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")
