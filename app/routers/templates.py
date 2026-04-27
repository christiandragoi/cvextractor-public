import logging
import os
import uuid
from pathlib import Path
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.database import get_db
from app.models.candidate import Template
from app.config import TEMPLATES_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Template).where(Template.is_active == True))
    rows = result.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "file_path": t.file_path,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]

@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only DOCX templates allowed")

    content = await file.read()
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    tpl_id = str(uuid.uuid4())
    safe_name = (name or file.filename).replace(" ", "_")
    file_path = TEMPLATES_DIR / f"{tpl_id}_{safe_name}"

    with open(file_path, "wb") as f:
        f.write(content)

    template = Template(
        id=tpl_id,
        name=name or file.filename,
        file_path=str(file_path),
        is_active=True,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "file_path": template.file_path,
        "is_active": template.is_active,
    }
