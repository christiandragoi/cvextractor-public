import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.candidate import Candidate
from app.config import UPLOADS_DIR

class CandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_candidate(self, filename: str, content: bytes, job_profile_id: str = None, recruiter_notes: str = None):
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        candidate = Candidate(
            full_name=None,
            first_name=None,
            last_name=None,
            nationality=None,
            email=None,
            phone=None,
            status="UPLOADED",
            original_filename=filename,
        )
        self.db.add(candidate)
        await self.db.commit()
        await self.db.refresh(candidate)

        file_path = UPLOADS_DIR / f"{candidate.id}_{filename}"
        with open(file_path, "wb") as f:
            f.write(content)
        candidate.original_file_path = str(file_path)
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate

    async def get_candidate(self, candidate_id: str):
        result = await self.db.execute(select(Candidate).where(Candidate.id == candidate_id))
        return result.scalar_one_or_none()
