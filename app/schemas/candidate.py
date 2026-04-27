from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel

class CandidateRead(BaseModel):
    id: str
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nationality: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    status: str
    original_filename: Optional[str] = None
    original_file_path: Optional[str] = None
    final_cv_path: Optional[str] = None
    template_id: Optional[str] = None
    extraction_model: Optional[str] = None
    extraction_provider: Optional[str] = None
    master_prompt: Optional[str] = None
    error_log: Optional[Any] = None
    needs_review: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
