from typing import List, Optional
from sqlalchemy.orm import Session
import logging

from app.core.errors import AppException, ErrorCode
from app.models import Taxonomy, TaxonomyEntry
from app.repositories import TaxonomyRepository, TaxonomyEntryRepository
from app.utils import validate_and_parse_excel

logger = logging.getLogger(__name__)



class TaxonomyService:
    def __init__(self, db: Session):
        self.db = db
        self.tax_repo = TaxonomyRepository(db)
        self.entry_repo = TaxonomyEntryRepository(db)

    def upload_taxonomy(
        self,
        file_contents: bytes,
        filename: str,
        sheet_name: str,
        taxonomy: str,
        description: str
    ) -> int:
        logger.info(
            "Uploading taxonomy",
            extra={"taxonomy": taxonomy, "sheet": sheet_name, "file": filename}
        )
        try:
            t = self.tax_repo.create(
                sheet_name=sheet_name,
                taxonomy=taxonomy,
                description=description,
                source_file=filename,
            )

            entries = []
            for row in validate_and_parse_excel(file_contents, sheet_name):
                entries.append({
                    "taxonomy_id": t.id,
                    "tag": row["tag"],
                    "datatype": row["type"],
                    "reference": row["reference"],
                })

            self.entry_repo.bulk_create(entries)
            self.db.commit()

            logger.info(
                "Uploaded taxonomy successfully",
                extra={"taxonomy_id": t.id, "taxonomy": taxonomy, "entries": len(entries)}
            )
            return t.id

        except Exception:
            logger.error(
                "Failed to upload taxonomy",
                extra={"taxonomy": taxonomy, "sheet": sheet_name, "file": filename},
                exc_info=True,
            )
            self.db.rollback()
            raise


    def get_by_taxonomy_name(self, taxonomy: str) -> Optional[Taxonomy]:
        return self.tax_repo.get_by_taxonomy(taxonomy)

    def get(self, taxonomy_id: int) -> Taxonomy:
        t = self.tax_repo.get(taxonomy_id)
        if not t:
            raise AppException(ErrorCode.NOT_FOUND, "Taxonomy not found", status_code=404)
        return t

    def delete(self, taxonomy_id: int) -> None:
        t = self.tax_repo.get(taxonomy_id)
        if not t:
            raise AppException(ErrorCode.NOT_FOUND, "Taxonomy not found", status_code=404)
        try:
            self.tax_repo.delete(t)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_entries(self, taxonomy_id: int) -> List[TaxonomyEntry]:
        return self.entry_repo.list_by_taxonomy(taxonomy_id)

    def add_entry(self, taxonomy_id: int, tag: str, datatype: str, reference: str) -> TaxonomyEntry:
        try:
            entry = self.entry_repo.create(taxonomy_id=taxonomy_id, tag=tag, datatype=datatype, reference=reference)
            self.db.commit()
            return entry
        except Exception:
            self.db.rollback()
            raise

    def update_entry(self, entry_id: int, tag: str, datatype: str, reference: str) -> TaxonomyEntry:
        entry = self.entry_repo.get(entry_id)
        if not entry:
            raise AppException(ErrorCode.NOT_FOUND, "Entry not found", status_code=404)
        try:
            updated = self.entry_repo.update(entry, tag=tag, datatype=datatype, reference=reference)
            self.db.commit()
            return updated
        except Exception:
            self.db.rollback()
            raise

    def delete_entry(self, entry_id: int) -> None:
        entry = self.entry_repo.get(entry_id)
        if not entry:
            raise AppException(ErrorCode.NOT_FOUND, "Entry not found", status_code=404)
        try:
            self.entry_repo.delete(entry)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
