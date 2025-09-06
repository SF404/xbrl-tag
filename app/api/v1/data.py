
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.taxonomy import UploadTaxonomyRequest, TaxonomyEntryRequest
from app.services.data_service import upload_taxonomy_service, get_taxonomy_service, delete_taxonomy_service, get_entries_service, add_entry_service, update_entry_service, delete_entry_service


router = APIRouter()

# ====== GET ========
@router.get("/{taxonomy_id}")
def get_taxonomy(taxonomy_id: int, db: Session = Depends(get_db)):
    return get_taxonomy_service(db, taxonomy_id)


@router.get("/{taxonomy_id}/entries")
def get_entries(taxonomy_id: int, db: Session = Depends(get_db)):
    return get_entries_service(db, taxonomy_id)


# ====== POST =======
@router.post("/upload")
async def upload_taxonomy(
    file: UploadFile = File(...),
    meta: UploadTaxonomyRequest = Depends(),
    db: Session = Depends(get_db),
):
    contents = await file.read()
    taxonomy_id = upload_taxonomy_service(
        db=db,
        file_contents=contents,
        filename=file.filename,
        sheet_name=meta.sheet_name,
        taxonomy=meta.taxonomy,
        description=meta.description,
    )
    return {"message": "Taxonomy uploaded successfully", "taxonomy_id": taxonomy_id}


@router.post("/{taxonomy_id}/entries")
def add_entry(taxonomy_id: int, req: TaxonomyEntryRequest, db: Session = Depends(get_db)):
    add_entry_service(db, taxonomy_id, req.tag, req.datatype, req.reference)
    return {"message": "Entry added successfully"}


# ====== PUT =======
@router.put("/entries/{entry_id}")
def update_entry(entry_id: int, req: TaxonomyEntryRequest, db: Session = Depends(get_db)):
    update_entry_service(db, entry_id, req.tag, req.datatype, req.reference)
    return {"message": "Entry updated successfully"}


# ====== DELETE =======
@router.delete("/{taxonomy_id}")
def delete_taxonomy(taxonomy_id: int, db: Session = Depends(get_db)):
    delete_taxonomy_service(db, taxonomy_id)
    return {"message": "Taxonomy deleted successfully"}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    delete_entry_service(db, entry_id)
    return {"message": "Entry deleted successfully"}
