import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.candidate import Candidate
from app.clients.ai_client import ai_client
from app.services.template_population_service import extract_text_from_bytes, TemplatePopulationService
from app.errors import ApiError, ErrorCode, ErrorStage, new_request_id
from app.config import OUTPUT_DIR, TEMPLATES_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/intake/process")
async def process_cv_intake(
    request: Request,
    cv_file: UploadFile = File(..., description="Candidate CV (PDF/DOCX)"),
    template_id: Optional[str] = Form(None, description="ID of the target Word template"),
    master_prompt: Optional[str] = Form(None, description="The extraction instructions to use"),
    ai_model: Optional[str] = Form("demo", description="AI model to use"),
    db: AsyncSession = Depends(get_db)
):
    """
    Full workflow:
    1. Create Candidate record
    2. Extract text from CV
    3. Call AIClient for structured data
    4. Populate Word template (if provided)
    5. Finalize Candidate record
    """
    request_id = getattr(request.state, "request_id", new_request_id())

    cv_filename = cv_file.filename or "cv_upload.pdf"
    candidate = Candidate(
        id=str(uuid.uuid4()),
        original_filename=cv_filename,
        original_file_path="",
        status="Extracting",
        extraction_model=ai_model,
        master_prompt=master_prompt,
        template_id=template_id,
    )

    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    try:
        # Save CV
        from app.config import UPLOADS_DIR
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        cv_path = UPLOADS_DIR / f"{candidate.id}_{cv_filename}"
        cv_bytes = await cv_file.read()
        with open(cv_path, "wb") as f:
            f.write(cv_bytes)
        candidate.original_file_path = str(cv_path)
        await db.commit()

        # Extract text
        cv_text = extract_text_from_bytes(cv_bytes, cv_filename)
        full_prompt = f"{master_prompt}\n\nCV TEXT CONTENT:\n{cv_text}" if master_prompt else cv_text

        # AI extraction
        extracted_data = await ai_client.extract_json(full_prompt, ai_model, request_id)

        # Resolve name fields
        resolved_name = (
            extracted_data.get("candidate", {}).get("full_name")
            or extracted_data.get("full_name")
            or extracted_data.get("name")
            or Path(cv_filename).stem.replace("_", " ").title()
        )

        # Split full_name into first/last if possible
        name_parts = resolved_name.split() if resolved_name else []
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        candidate.full_name = resolved_name
        candidate.first_name = first_name
        candidate.last_name = last_name
        candidate.nationality = extracted_data.get("candidate", {}).get("nationality") or extracted_data.get("nationality")
        candidate.email = extracted_data.get("candidate", {}).get("email") or extracted_data.get("email")
        candidate.phone = extracted_data.get("candidate", {}).get("phone") or extracted_data.get("phone")
        candidate.date_of_birth = extracted_data.get("candidate", {}).get("date_of_birth") or extracted_data.get("date_of_birth")
        candidate.place_of_birth = extracted_data.get("candidate", {}).get("place_of_birth") or extracted_data.get("place_of_birth")
        candidate.error_log = extracted_data
        candidate.status = "Rendering Template"
        await db.commit()

        # Phase B: Template population
        final_docx_path = None
        if template_id:
            from app.models.candidate import Template as TemplateModel
            tpl_obj = await db.get(TemplateModel, template_id)
            if tpl_obj and tpl_obj.file_path and os.path.exists(tpl_obj.file_path):
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                output_filename = f"{resolved_name.replace(' ', '_')}_Final.docx"
                output_path = OUTPUT_DIR / f"{candidate.id}_{output_filename}"

                populator = TemplatePopulationService(tpl_obj.file_path)
                populator.save(extracted_data, str(output_path))
                final_docx_path = str(output_path)
                candidate.final_cv_path = final_docx_path

        candidate.status = "Ready for Review"
        await db.commit()
        await db.refresh(candidate)

        return {
            "success": True,
            "candidate_id": candidate.id,
            "full_name": candidate.full_name,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "status": candidate.status,
            "final_cv_path": final_docx_path,
            "data": extracted_data
        }

    except Exception as e:
        logger.error(f"Extraction failed for candidate {candidate.id}: {e}", exc_info=True)
        candidate.status = "Failed"
        error_msg = str(e.detail) if hasattr(e, "detail") else str(e)
        candidate.error_log = {"error": error_msg}
        await db.commit()
        if isinstance(e, ApiError):
            raise e
        raise ApiError(
            status_code=500,
            code=ErrorCode.UNEXPECTED_ERROR,
            message=str(e),
            stage=ErrorStage.LLM_INFERENCE,
            request_id=request_id,
            retryable=False
        )


@router.post("/process")
async def process_extraction_legacy(
    request: Request,
    cv_file: UploadFile = File(..., description="Candidate CV (PDF/DOCX)"),
    template_id: Optional[str] = Form(None),
    master_prompt: Optional[str] = Form(None),
    ai_model: Optional[str] = Form("demo"),
    db: AsyncSession = Depends(get_db)
):
    """Legacy /api/process endpoint."""
    return await process_cv_intake(request, cv_file, template_id, master_prompt, ai_model, db)


@router.get("/download/{candidate_id}")
async def download_candidate_docx(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Download the generated DOCX."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate or not candidate.final_cv_path or not os.path.exists(candidate.final_cv_path):
        raise HTTPException(status_code=404, detail="Generated document not found.")

    return FileResponse(
        path=candidate.final_cv_path,
        filename=f"{candidate.full_name or 'Candidate'}_CV_Final.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
