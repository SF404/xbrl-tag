import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query as Q
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.errors import AppException, ErrorCode
from app.repositories.feedback import FeedbackRepository
from app.repositories.taxonomy import TaxonomyRepository
from app.schemas.schemas import (
    FeedbackCreateRequest,
    FeedbackUpdateRequest,
    FeedbackResponse,
    MessageResponse,
    FeedbackListQuery,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback")


@router.get("", response_model=List[FeedbackResponse])
def list_feedback(
    params: FeedbackListQuery = Depends(),
    db: Session = Depends(get_db),
):
    repo = FeedbackRepository(db)

    # taxonomy filter (optional)
    tax_id: Optional[int] = None
    if params.taxonomy:
        t = TaxonomyRepository(db).get_by_taxonomy(params.taxonomy)
        if not t:
            logger.info(
                "List feedback: taxonomy not found",
                extra={"taxonomy": params.taxonomy},
            )
            return []  # keep existing behavior
        tax_id = t.id

    # validate date range if both provided
    if params.date_from and params.date_to and params.date_from > params.date_to:
        logger.warning(
            "Invalid date range for list_feedback",
            extra={"date_from": str(params.date_from), "date_to": str(params.date_to)},
        )
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "'date_from' must be <= 'date_to'",
            status_code=422,
        )

    items = repo.list_filtered(
        taxonomy_id=tax_id,
        date_from=params.date_from,
        date_to=params.date_to,
        offset=params.offset,
        limit=params.limit,
    )
    logger.info(
        "List feedback completed",
        extra={
            "taxonomy": params.taxonomy,
            "date_from": str(params.date_from) if params.date_from else None,
            "date_to": str(params.date_to) if params.date_to else None,
            "returned": len(items),
        },
    )
    return [FeedbackResponse.model_validate(it, from_attributes=True) for it in items]


@router.post("", response_model=FeedbackResponse)
def create_feedback(payload: FeedbackCreateRequest, db: Session = Depends(get_db)):
    tax = TaxonomyRepository(db).get_by_taxonomy(payload.taxonomy)
    if not tax:
        logger.warning(
            "Create feedback: unknown taxonomy",
            extra={"taxonomy": payload.taxonomy},
        )
        raise AppException(
            ErrorCode.NOT_FOUND,
            f"Unknown taxonomy '{payload.taxonomy}'",
            status_code=404,
        )

    try:
        repo = FeedbackRepository(db)
        obj = repo.create(
            taxonomy_id=tax.id,
            query=payload.query,
            reference=payload.reference,
            tag=payload.tag,
            is_correct=payload.is_correct,
            is_custom=payload.is_custom,
            rank=payload.rank,
        )
        db.commit()
        db.refresh(obj)  # ensure created_at/defaults populated
        logger.info(
            "Feedback created",
            extra={"feedback_id": obj.id, "taxonomy": payload.taxonomy},
        )
        return FeedbackResponse.model_validate(obj, from_attributes=True)
    except Exception:
        db.rollback()
        logger.error(
            "Failed to create feedback",
            extra={"taxonomy": payload.taxonomy},
            exc_info=True,
        )
        raise


@router.patch("", response_model=FeedbackResponse)
def update_feedback(payload: FeedbackUpdateRequest, db: Session = Depends(get_db)):
    repo = FeedbackRepository(db)
    obj = repo.get(payload.id)
    if not obj:
        logger.warning("Update feedback: not found", extra={"feedback_id": payload.id})
        raise AppException(ErrorCode.NOT_FOUND, "Feedback not found", status_code=404)

    try:
        updated = repo.update(
            obj,
            query=payload.query if payload.query is not None else obj.query,
            reference=payload.reference if payload.reference is not None else obj.reference,
            tag=payload.tag if payload.tag is not None else obj.tag,
            is_correct=payload.is_correct if payload.is_correct is not None else obj.is_correct,
            is_custom=payload.is_custom if payload.is_custom is not None else obj.is_custom,
            rank=payload.rank if payload.rank is not None else obj.rank,
        )
        db.commit()
        db.refresh(updated)
        logger.info("Feedback updated", extra={"feedback_id": payload.id})
        return FeedbackResponse.model_validate(updated, from_attributes=True)
    except Exception:
        db.rollback()
        logger.error("Failed to update feedback", extra={"feedback_id": payload.id}, exc_info=True)
        raise


@router.delete("", response_model=MessageResponse)
def delete_feedback(id: int = Q(..., description="feedback id"), db: Session = Depends(get_db)):
    repo = FeedbackRepository(db)
    obj = repo.get(id)
    if not obj:
        logger.warning("Delete feedback: not found", extra={"feedback_id": id})
        raise AppException(ErrorCode.NOT_FOUND, "Feedback not found", status_code=404)

    try:
        repo.delete(obj)
        db.commit()
        logger.info("Feedback deleted", extra={"feedback_id": id})
        return MessageResponse(message="Deleted.")
    except Exception:
        db.rollback()
        logger.error("Failed to delete feedback", extra={"feedback_id": id}, exc_info=True)
        raise
