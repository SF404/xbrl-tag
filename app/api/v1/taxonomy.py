from typing import List

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.managers.index_cache_manager import index_cache
from app.core.errors import AppException, ErrorCode
from app.repositories.taxonomy import TaxonomyRepository
from app.repositories.taxonomy_entry import TaxonomyEntryRepository
from app.services.taxonomy_service import TaxonomyService
from app.schemas.schemas import (
    TaxonomyResponse,
    TaxonomyEntryResponse,
    AddEntryRequest,
    UpdateEntryRequest,
    UploadTaxonomyResponse,
    UploadTaxonomyRequest,
    MessageResponse,
)

router = APIRouter(prefix="/taxonomy")


@router.post("/upload", response_model=UploadTaxonomyResponse)
async def upload_taxonomy(
    file: UploadFile = File(),
    meta: UploadTaxonomyRequest = Depends(),
    db: Session = Depends(get_db),
):
    """
    Upload a new taxonomy from a file.
    """
    try:
        data = await file.read()
        svc = TaxonomyService(db)
        taxonomy_id = svc.upload_taxonomy(
            file_contents=data,
            filename=file.filename,
            sheet_name=meta.sheet_name,
            taxonomy=meta.taxonomy,
            description=meta.description,
        )
        return UploadTaxonomyResponse(taxonomy_id=taxonomy_id)
    except Exception as e:
        raise AppException(
            ErrorCode.INTERNAL_SERVER_ERROR,
            f"Failed to process taxonomy upload: {e}",
            status_code=500,
        )


@router.get("/list", response_model=List[TaxonomyResponse])
def list_taxonomies(db: Session = Depends(get_db)):
    """
    Retrieve a list of all taxonomies.
    """
    items = TaxonomyRepository(db).list()
    return [TaxonomyResponse.model_validate(x, from_attributes=True) for x in items]


@router.get("/{taxonomy_id}", response_model=TaxonomyResponse)
def get_taxonomy(taxonomy_id: int, db: Session = Depends(get_db)):
    """
    Get a single taxonomy by its ID.
    """
    t = TaxonomyService(db).get(taxonomy_id)
    return TaxonomyResponse.model_validate(t, from_attributes=True)


@router.delete("/{taxonomy_id}", response_model=MessageResponse)
def delete_taxonomy(taxonomy_id: int, db: Session = Depends(get_db)):
    """
    Delete a taxonomy by its ID.
    """
    repo = TaxonomyRepository(db)
    t = repo.get(taxonomy_id)
    if not t:
        raise AppException(ErrorCode.NOT_FOUND, "Taxonomy not found", status_code=404)
    
    taxonomy_key = t.taxonomy
    TaxonomyService(db).delete(taxonomy_id)
    index_cache.remove(taxonomy_key, from_disk=True)
    return MessageResponse(message="Deleted (with cascade).")


@router.get("/{taxonomy_id}/entries", response_model=List[TaxonomyEntryResponse])
def get_taxonomy_entries(
    taxonomy_id: int, offset: int = 0, limit: int = 200, db: Session = Depends(get_db)
):
    """
    Get entries for a specific taxonomy.
    """
    entries = TaxonomyService(db).get_entries(taxonomy_id)[offset : offset + limit]
    return [TaxonomyEntryResponse.model_validate(x, from_attributes=True) for x in entries]


@router.post("/entries", response_model=TaxonomyEntryResponse)
def add_entry(payload: AddEntryRequest, db: Session = Depends(get_db)):
    """
    Add a new entry to a taxonomy.
    """
    e = TaxonomyService(db).add_entry(
        taxonomy_id=payload.taxonomy_id,
        tag=payload.tag,
        datatype=payload.datatype,
        reference=payload.reference,
    )
    return TaxonomyEntryResponse.model_validate(e, from_attributes=True)


@router.patch("/entries/{entry_id}", response_model=TaxonomyEntryResponse)
def update_entry(
    entry_id: int, payload: UpdateEntryRequest, db: Session = Depends(get_db)
):
    """
    Update an existing taxonomy entry.
    """
    entry_repo = TaxonomyEntryRepository(db)
    current = entry_repo.get(entry_id)
    
    if not current:
        raise AppException(ErrorCode.NOT_FOUND, "Entry not found", status_code=404)
    
    e = TaxonomyService(db).update_entry(
        entry_id=entry_id,
        tag=payload.tag if payload.tag is not None else current.tag,
        datatype=payload.datatype if payload.datatype is not None else current.datatype,
        reference=payload.reference if payload.reference is not None else current.reference,
    )
    return TaxonomyEntryResponse.model_validate(e, from_attributes=True)


@router.delete("/entries/{entry_id}", response_model=MessageResponse)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    """
    Delete a taxonomy entry.
    """
    TaxonomyService(db).delete_entry(entry_id)
    return MessageResponse(message="Deleted.")