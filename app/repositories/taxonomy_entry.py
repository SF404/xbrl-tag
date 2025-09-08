from typing import List, Optional, Iterable
from .base import BaseRepository
from app.models.entities import TaxonomyEntry


class TaxonomyEntryRepository(BaseRepository):
    def get(self, id: int) -> Optional[TaxonomyEntry]:
        return self.db.query(TaxonomyEntry).get(id)  # type: ignore[attr-defined]

    def list_by_taxonomy(self, taxonomy_id: int, offset: int = 0, limit: int = 200) -> List[TaxonomyEntry]:
        return (
            self.db.query(TaxonomyEntry)
            .filter(TaxonomyEntry.taxonomy_id == taxonomy_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def create(
        self, taxonomy_id: int, tag: str, datatype: str | None = None, reference: str | None = None
    ) -> TaxonomyEntry:
        obj = TaxonomyEntry(taxonomy_id=taxonomy_id, tag=tag, datatype=datatype, reference=reference)
        return self.add(obj)

    def bulk_create(self, items: Iterable[dict]) -> List[TaxonomyEntry]:
        objs = [TaxonomyEntry(**it) for it in items]
        self.db.add_all(objs)
        self.db.flush()
        return objs
    
    def update(self, obj: TaxonomyEntry, **fields) -> TaxonomyEntry:
        for k, v in fields.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj
    
    def count_by_taxonomy(self, taxonomy_id: int) -> int:
        return (
            self.db.query(TaxonomyEntry)
            .filter(TaxonomyEntry.taxonomy_id == taxonomy_id)
            .count()
    )
