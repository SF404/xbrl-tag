from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Embedder
from app.repositories import EmbedderRepository

class EmbedderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EmbedderRepository(db)

    def list(self) -> List:
        return self.repo.list()

    def delete(self, embedder_id: int) -> Optional[Embedder]:
        obj = self.repo.get(embedder_id)
        if obj:
            try:
                self.repo.delete(obj)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return obj
