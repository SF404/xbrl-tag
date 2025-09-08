from typing import List, Optional
from sqlalchemy.orm import Session
from .base import BaseRepository
from app.models.entities import Reranker


class RerankerRepository(BaseRepository):
    def get(self, id: int) -> Optional[Reranker]:
        return self.db.query(Reranker).get(id)

    def list(self, offset: int = 0, limit: int = 100) -> List[Reranker]:
        return self.db.query(Reranker).offset(offset).limit(limit).all()

    def get_active(self) -> List[Reranker]:
        return self.db.query(Reranker).filter(Reranker.is_active.is_(True)).all()

    def create(
        self, name: str, version: str, path: str, normalize_method: str | None = None, is_active: bool = True
    ) -> Reranker:
        obj = Reranker(
            name=name,
            version=version,
            path=path,
            normalize_method=normalize_method,
            is_active=is_active,
        )
        return self.add(obj)

    def update(self, obj: Reranker, **fields) -> Reranker:
        for k, v in fields.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj
