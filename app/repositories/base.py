from typing import Any
from sqlalchemy.orm import Session


class BaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, instance: Any) -> Any:
        self.db.add(instance)
        self.db.flush()
        return instance

    def delete(self, instance: Any) -> Any:
        self.db.delete(instance)
        return instance

    def get_by_id(self, model, id: int):
        return self.db.query(model).get(id)
