from typing import List, Optional
from .base import BaseRepository
from app.models.entities import Taxonomy


class TaxonomyRepository(BaseRepository):
    def get(self, id: int) -> Optional[Taxonomy]:
        return self.db.query(Taxonomy).get(id)

    def get_by_taxonomy(self, taxonomy_name: str) -> Optional[Taxonomy]:
        return self.db.query(Taxonomy).filter(Taxonomy.taxonomy == taxonomy_name).one_or_none()

    def list(self) -> List[Taxonomy]:
        return self.db.query(Taxonomy).all()

    def create(
        self, sheet_name: str,
        taxonomy: str,
        description: str | None = None,
        source_file: str | None = None
    ) -> Taxonomy:
        obj = Taxonomy(
            sheet_name=sheet_name,
            taxonomy=taxonomy,
            description=description,
            source_file=source_file,
        )
        return self.add(obj)

    def update(self, obj: Taxonomy, **fields) -> Taxonomy:
        for k, v in fields.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj
