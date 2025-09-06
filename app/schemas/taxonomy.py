from pydantic import BaseModel

class UploadTaxonomyRequest(BaseModel):
    taxonomy: str
    description: str
    sheet_name: str


class TaxonomyEntryRequest(BaseModel):
    tag: str
    datatype: str
    reference: str
