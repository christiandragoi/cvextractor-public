from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class ExtractionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class CVData(BaseModel):
    """German CV structure"""
    full_name: str = Field("", description="Vollständiger Name")
    email: Optional[str] = Field(None, description="E-Mail-Adresse")
    phone: Optional[str] = Field(None, description="Telefonnummer")
    address: Optional[str] = Field(None, description="Adresse")
    berufsbezeichnung: Optional[str] = Field(None, description="Job title/Profession")
    geburtsdatum: Optional[str] = Field(None, description="Date of birth")
    staatsangehoerigkeit: Optional[str] = Field(None, description="Nationality")
    fuhrerschein: Optional[str] = Field(None, description="Driver's license categories")
    ausbildung: List[dict] = Field(default_factory=list, description="Education/Training")
    berufserfahrung: List[dict] = Field(default_factory=list, description="Work experience")
    sprachen: List[dict] = Field(default_factory=list, description="Language skills")
    schluesselqualifikationen: List[str] = Field(default_factory=list, description="Key skills")

class FieldConfidence(BaseModel):
    field: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    warning: Optional[str] = None

class ExtractionResult(BaseModel):
    file_id: str
    filename: str
    status: ExtractionStatus
    cv_data: Optional[CVData] = None
    confidence_scores: List[FieldConfidence] = []
    processing_time: Optional[float] = None  # seconds
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    
    # German compliance fields
    processing_method: Literal["ollama_local", "fallback"] = "ollama_local"
    datenschutz_hinweis: str = "Verarbeitet lokal via Ollama - keine Datenübertragung an Dritte"

class BatchRequest(BaseModel):
    files: List[str]  # File IDs uploaded via /upload
    template_type: Literal["standard", "ap_bau", "zeitarbeit"] = "standard"

class BatchProgress(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    current_file: Optional[str] = None
    progress_percent: int
