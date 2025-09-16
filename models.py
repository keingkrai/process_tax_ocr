from pydantic import BaseModel
from typing import Dict, Any

class Meta(BaseModel):
    original_name: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    sha256: str

class InsertDocumentRequest(BaseModel):
    employee_id: int
    member_name: str
    meta: Meta
    result_json: Dict[str, Any]
