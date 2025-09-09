from typing import List, Optional, Tuple
from datetime import date, timedelta, datetime

from .base import BaseRepository
from app.models import Feedback

class FeedbackRepository(BaseRepository):
    def get(self, id: int) -> Optional[Feedback]:
        return self.db.query(Feedback).get(id)
    

    def list_by_taxonomy(self, taxonomy_id: int, offset: int = 0, limit: int = 200) -> List[Feedback]:
        return (
            self.db.query(Feedback)
            .filter(Feedback.taxonomy_id == taxonomy_id)
            .order_by(Feedback.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )



    def list_filtered(
            self,
            taxonomy_id: Optional[int],
            date_from: Optional[date],
            date_to: Optional[date],
            pagination: bool = True,
            offset: int = 0,
            limit: int = 200,
        ) -> List[Feedback]:
        q = self.db.query(Feedback)

        if taxonomy_id is not None:
            q = q.filter(Feedback.taxonomy_id == taxonomy_id)

        # >= date_from 00:00
        if date_from is not None:
            start = datetime.combine(date_from, datetime.min.time())
            q = q.filter(Feedback.created_at >= start)

        # < (date_to + 1 day) 00:00  (inclusive end-of-day)
        if date_to is not None:
            end = datetime.combine(date_to + timedelta(days=1), datetime.min.time())
            q = q.filter(Feedback.created_at < end)

        # Apply pagination if the flag is True
        if pagination:
            return (
                q.order_by(Feedback.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
        else:
            return q.order_by(Feedback.created_at.desc()).all()



    def create(
        self,
        taxonomy_id: int,
        query: str,
        reference: str | None,
        tag: str,
        is_correct: bool,
        is_custom: bool = False,
        rank: int | None = None,
    ) -> Feedback:
        obj = Feedback(
            taxonomy_id=taxonomy_id,
            query=query,
            reference=reference,
            tag=tag,
            is_correct=is_correct,
            is_custom=is_custom,
            rank=rank,
        )
        return self.add(obj)

    def update(self, obj: Feedback, **fields) -> Feedback:
        for k, v in fields.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj

    def delete(self, obj: Feedback) -> Feedback:
        self.db.delete(obj)
        return obj
