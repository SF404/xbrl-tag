from typing import List, Optional

from .base import BaseRepository
from app.models.entities import Embedder


class EmbedderRepository(BaseRepository):
    def get(self, id: int) -> Optional[Embedder]:
        return self.db.query(Embedder).get(id)

    def list(self, offset: int = 0, limit: int = 100) -> List[Embedder]:
        return self.db.query(Embedder).offset(offset).limit(limit).all()

    def create(self, name: str, version: str, path: str, is_active: bool = True) -> Embedder:
        obj = Embedder(name=name, version=version, path=path, is_active=is_active)
        return self.add(obj)

    def update(self, obj: Embedder, **fields) -> Embedder:
        for k, v in fields.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj
