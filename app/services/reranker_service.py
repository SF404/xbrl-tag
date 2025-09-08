from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Reranker
from app.repositories import RerankerRepository


class RerankerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RerankerRepository(db)

    def list(self) -> List:
        return self.repo.list()

    def delete(self, rid: int) -> Optional[Reranker]:
        obj = self.get(rid)
        if obj:
            try:
                self.repo.delete(obj)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return obj
