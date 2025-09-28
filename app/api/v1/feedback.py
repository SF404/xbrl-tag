import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_access_level
from app.core.errors import AppException, ErrorCode
from app.repositories.feedback import FeedbackRepository
from app.repositories.taxonomy import TaxonomyRepository
from app.schemas.schemas import (
    FeedbackCreateRequest,
    FeedbackListQuery,
    FeedbackResponse,
    FeedbackUpdateRequest,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback")


@router.get("", response_model=List[FeedbackResponse])
def list_feedback(
    params: FeedbackListQuery = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_access_level(7))
):
    """
    Lists feedback entries, with optional filters for taxonomy and date range.
    """
    repo = FeedbackRepository(db)

    # Resolve taxonomy name to ID if provided
    tax_id: Optional[int] = None
    if params.taxonomy:
        t = TaxonomyRepository(db).get_by_taxonomy(params.taxonomy)
        if not t:
            logger.info(
                "List feedback: taxonomy not found, returning empty list.",
                extra={"taxonomy": params.taxonomy},
            )
            return []
        tax_id = t.id

    # Validate date range
    if params.date_from and params.date_to and params.date_from > params.date_to:
        logger.warning(
            "Invalid date range for list_feedback",
            extra={"date_from": str(params.date_from), "date_to": str(params.date_to)},
        )
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "'date_from' must be on or before 'date_to'",
            status_code=422,
        )

    # Fetch filtered items from the repository
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
            "returned_count": len(items),
        },
    )
    return [FeedbackResponse.model_validate(it, from_attributes=True) for it in items]


@router.post("", response_model=FeedbackResponse)
def create_feedback(payload: FeedbackCreateRequest, db: Session = Depends(get_db)):
    """
    Creates a new feedback entry.
    """
    # Ensure the specified taxonomy exists
    tax = TaxonomyRepository(db).get_by_taxonomy(payload.taxonomy)
    if not tax:
        logger.warning(
            "Create feedback: unknown taxonomy", extra={"taxonomy": payload.taxonomy}
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
        db.refresh(obj)  # Populate fields with server-side defaults (e.g., created_at)
        logger.info(
            "Feedback created successfully",
            extra={"feedback_id": obj.id, "taxonomy": payload.taxonomy},
        )
        return FeedbackResponse.model_validate(obj, from_attributes=True)
    except Exception:
        db.rollback()
        logger.error(
            "Failed to create feedback due to a database error",
            extra={"taxonomy": payload.taxonomy},
            exc_info=True,
        )
        raise


@router.patch("", response_model=FeedbackResponse)
def update_feedback(payload: FeedbackUpdateRequest, db: Session = Depends(get_db)):
    """
    Updates an existing feedback entry.
    """
    repo = FeedbackRepository(db)

    # Find the existing feedback object
    obj = repo.get(payload.id)
    if not obj:
        logger.warning(
            "Update feedback: not found", extra={"feedback_id": payload.id}
        )
        raise AppException(ErrorCode.NOT_FOUND, "Feedback not found", status_code=404)

    try:
        # Apply updates, keeping existing values for fields not provided in the payload
        updated = repo.update(
            obj,
            query=payload.query if payload.query is not None else obj.query,
            reference=(
                payload.reference if payload.reference is not None else obj.reference
            ),
            tag=payload.tag if payload.tag is not None else obj.tag,
            is_correct=(
                payload.is_correct if payload.is_correct is not None else obj.is_correct
            ),
            is_custom=(
                payload.is_custom if payload.is_custom is not None else obj.is_custom
            ),
            rank=payload.rank if payload.rank is not None else obj.rank,
        )
        db.commit()
        db.refresh(updated)
        logger.info("Feedback updated successfully", extra={"feedback_id": payload.id})
        return FeedbackResponse.model_validate(updated, from_attributes=True)
    except Exception:
        db.rollback()
        logger.error(
            "Failed to update feedback due to a database error",
            extra={"feedback_id": payload.id},
            exc_info=True,
        )
        raise


@router.delete("", response_model=MessageResponse)
def delete_feedback(
    id: int = Query(..., description="ID of the feedback to delete"),
    db: Session = Depends(get_db),
):
    """
    Deletes a feedback entry by its ID.
    """
    repo = FeedbackRepository(db)

    # Find the existing feedback object
    obj = repo.get(id)
    if not obj:
        logger.warning("Delete feedback: not found", extra={"feedback_id": id})
        raise AppException(ErrorCode.NOT_FOUND, "Feedback not found", status_code=404)

    try:
        repo.delete(obj)
        db.commit()
        logger.info("Feedback deleted successfully", extra={"feedback_id": id})
        return MessageResponse(message="Deleted.")
    except Exception:
        db.rollback()
        logger.error(
            "Failed to delete feedback due to a database error",
            extra={"feedback_id": id},
            exc_info=True,
        )
        raise
