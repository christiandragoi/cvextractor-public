import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, JSON
from app.database import Base

class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    nationality = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)
    place_of_birth = Column(String, nullable=True)
    status = Column(String, default="UPLOADED")
    original_filename = Column(String, nullable=True)
    original_file_path = Column(String, nullable=True)
    final_cv_path = Column(String, nullable=True)
    template_id = Column(String, nullable=True)
    extraction_model = Column(String, nullable=True)
    extraction_provider = Column(String, nullable=True)
    master_prompt = Column(Text, nullable=True)
    error_log = Column(JSON, nullable=True)
    needs_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "nationality": self.nationality,
            "email": self.email,
            "phone": self.phone,
            "date_of_birth": self.date_of_birth,
            "place_of_birth": self.place_of_birth,
            "status": self.status,
            "original_filename": self.original_filename,
            "original_file_path": self.original_file_path,
            "final_cv_path": self.final_cv_path,
            "template_id": self.template_id,
            "extraction_model": self.extraction_model,
            "extraction_provider": self.extraction_provider,
            "master_prompt": self.master_prompt,
            "error_log": self.error_log,
            "needs_review": self.needs_review,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
