import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.deps import get_jobs_manager, get_registry, require_access_level
from app.core.errors import AppException, ErrorCode
from app.managers.index_cache_manager import index_cache
from app.schemas.schemas import (
    BuildIndexRequest,
    CacheStatsResponse,
    FineTuneEmbedderRequest,
    FineTuneRerankerRequest,
)
from app.services import (
    build_index_async,
    finetune_embedder_async,
    finetune_reranker_async,
)

router = APIRouter(prefix="/jobs")


@router.post("/build_index")
def build_index(
    req: BuildIndexRequest,
    background_tasks: BackgroundTasks,
    registry=Depends(get_registry),
    jobs=Depends(get_jobs_manager),
    # This dependency enforces an access level of 7+ but isn't used directly.
    _admin_user=Depends(require_access_level(7)),
):
    """
    Starts a background job to build a FAISS index for a given taxonomy.

    Prevents duplicate builds for the same taxonomy if one is already running.
    Requires admin-level access.
    """
    if not req.taxonomy:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "taxonomy is required", status_code=422
        )
    if not registry or not registry.embedder:
        raise AppException(
            ErrorCode.MODEL_NOT_LOADED, "Active embedder not loaded", status_code=500
        )

    # Prevent duplicate concurrent builds for the same taxonomy
    active = jobs.find_active_for_taxonomy(req.taxonomy)
    if active:
        jid, state = active
        return {
            "message": "Build already running for this taxonomy",
            "job_id": jid,
            "status": state["status"],
        }

    # Create and queue the new job
    job_id = str(uuid.uuid4())
    jobs.set(
        job_id,
        {
            "status": "queued",
            "progress": 0,
            "total": 0,
            "done": 0,
            "taxonomy": req.taxonomy,
        },
    )

    background_tasks.add_task(build_index_async, job_id, req.taxonomy, registry, jobs)
    return {"message": "Index build started", "job_id": job_id}


@router.post("/finetune_embedder")
def finetune_embedder(
    req: FineTuneEmbedderRequest,
    background_tasks: BackgroundTasks,
    jobs=Depends(get_jobs_manager),
):
    """
    Starts a background job to fine-tune an embedder model using feedback data.
    """
    if not req.embedder_id:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "embedder_id is required", status_code=422
        )

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

    # Add the task to the background to perform fine-tuning
    background_tasks.add_task(
        finetune_embedder_async, job_id, req.embedder_id, req.date_from, req.date_to, jobs
    )

    return {"message": "Embedder fine-tuning job started", "job_id": job_id}


@router.post("/finetune_reranker")
def finetune_reranker(
    req: FineTuneRerankerRequest,
    background_tasks: BackgroundTasks,
    jobs=Depends(get_jobs_manager),
):
    """
    Starts a background job to fine-tune a reranker model using feedback data.
    """
    if not req.reranker_id:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "reranker_id is required", status_code=422
        )

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

    background_tasks.add_task(
        finetune_reranker_async, job_id, req.reranker_id, req.date_from, req.date_to, jobs
    )

    return {"message": "Reranker fine-tuning job started", "job_id": job_id}


@router.get("/status/all")
def get_all_jobs(jobs=Depends(get_jobs_manager)):
    """Returns the status of all jobs."""
    return jobs.all()


@router.get("/status/{job_id}")
def get_job_status(job_id: str, jobs=Depends(get_jobs_manager)):
    """Returns the status of a specific job by its ID."""
    data = jobs.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return data


@router.get("/index_cache/stats", response_model=CacheStatsResponse)
def get_cache_stats():
    """Retrieves statistics about the index cache."""
    try:
        stats = index_cache.get_stats()
        # Ensure Path object is converted to string for JSON serialization
        stats["index_path"] = str(stats["index_path"])
        return CacheStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )
