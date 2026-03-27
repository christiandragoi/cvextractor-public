from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, WebSocket
from fastapi.responses import JSONResponse
from typing import List
import uuid
import os
import asyncio
from datetime import datetime
import json

from app.models.schemas import ExtractionResult, BatchRequest, BatchProgress, ExtractionStatus
from app.services.ollama_client import OllamaClient
from app.services.parser import DocumentParser
from app.services.extractor import CVExtractorService

router = APIRouter()
ollama = OllamaClient()
parser = DocumentParser()
extractor = CVExtractorService(ollama, parser)

# In-memory storage for demo (use Redis in production)
processing_jobs = {}

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload files to temp storage, return IDs for processing"""
    file_ids = []
    
    for file in files:
        file_id = str(uuid.uuid4())
        ext = file.filename.split('.')[-1].lower()
        
        if ext not in ['pdf', 'docx', 'doc', 'txt']:
            raise HTTPException(400, f"Nicht unterstütztes Format: {ext}")
        
        # Save to temp directory
        file_path = f"uploads/{file_id}.{ext}"
        os.makedirs("uploads", exist_ok=True)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        file_ids.append({
            "file_id": file_id,
            "filename": file.filename,
            "size": len(content),
            "path": file_path
        })
    
    return {"files": file_ids}

@router.post("/extract/{file_id}")
async def extract_single(file_id: str, background_tasks: BackgroundTasks):
    """Process single CV asynchronously"""
    
    # Check if file exists
    file_path = None
    for ext in ['pdf', 'docx', 'doc']:
        path = f"uploads/{file_id}.{ext}"
        if os.path.exists(path):
            file_path = path
            break
    
    if not file_path:
        raise HTTPException(404, "Datei nicht gefunden")
    
    # Initialize job status
    job_id = str(uuid.uuid4())
    processing_jobs[job_id] = {
        "file_id": file_id,
        "status": ExtractionStatus.PROCESSING,
        "progress": 0,
        "result": None
    }
    
    # Process in background (or use Celery for production)
    background_tasks.add_task(process_cv_job, job_id, file_path)
    
    return {"job_id": job_id, "status": "processing"}

async def process_cv_job(job_id: str, file_path: str):
    """Background processing with progress updates"""
    start_time = datetime.now()
    
    try:
        # Read file
        with open(file_path, "rb") as f:
            content = f.read()
        
        # Update progress
        processing_jobs[job_id]["progress"] = 10
        
        # Parse document
        ext = file_path.split('.')[-1]
        if ext == 'pdf':
            text = await parser.parse_pdf(content)
        else:
            text = await parser.parse_docx(content)
        
        processing_jobs[job_id]["progress"] = 30
        
        # Quality check
        quality_issues = parser.detect_quality_issues(text)
        if quality_issues:
            processing_jobs[job_id]["warnings"] = quality_issues
        
        # AI Extraction
        async def progress_update(step: str):
            if step == "contacting_ollama":
                processing_jobs[job_id]["progress"] = 50
            elif step == "parsing_response":
                processing_jobs[job_id]["progress"] = 80
        
        result = await ollama.extract_cv_data(text, progress_callback=progress_update)
        
        processing_jobs[job_id]["progress"] = 100
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Build response
        extraction_result = ExtractionResult(
            file_id=job_id,
            filename=os.path.basename(file_path),
            status=ExtractionStatus.COMPLETED,
            cv_data=result["data"],
            confidence_scores=[
                {"field": k, "value": str(v)[:50], "confidence": result["confidence"].get(k, 0.5)}
                for k, v in result["data"].items()
            ],
            processing_time=processing_time,
            completed_at=datetime.now(),
            warnings=result.get("warnings", [])
        )
        
        processing_jobs[job_id]["result"] = extraction_result.dict()
        processing_jobs[job_id]["status"] = ExtractionStatus.COMPLETED
        
        # Cleanup file after processing (GDPR)
        os.remove(file_path)
        
    except Exception as e:
        processing_jobs[job_id]["status"] = ExtractionStatus.ERROR
        processing_jobs[job_id]["error"] = str(e)
        processing_jobs[job_id]["progress"] = 100

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check processing status"""
    if job_id not in processing_jobs:
        raise HTTPException(404, "Job nicht gefunden")
    
    job = processing_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "result": job.get("result"),
        "error": job.get("error")
    }

@router.websocket("/ws/batch/{batch_id}")
async def websocket_batch_progress(websocket: WebSocket, batch_id: str):
    """
    WebSocket for real-time batch processing updates.
    Frontend connects here to get live progress bars.
    """
    await websocket.accept()
    
    try:
        while True:
            # Check batch status (implement with Redis/DB in production)
            if batch_id in processing_jobs:
                await websocket.send_json({
                    "type": "progress",
                    "data": processing_jobs[batch_id]
                })
            
            await asyncio.sleep(1)  # Poll every second
            
    except Exception as e:
        await websocket.close()

@router.post("/batch")
async def process_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """Process multiple files with queue management"""
    batch_id = str(uuid.uuid4())
    
    processing_jobs[batch_id] = {
        "batch_id": batch_id,
        "total": len(request.files),
        "completed": 0,
        "failed": 0,
        "current_file": None,
        "progress_percent": 0,
        "results": []
    }
    
    # Queue all files
    for file_id in request.files:
        background_tasks.add_task(process_batch_item, batch_id, file_id)
    
    return {"batch_id": batch_id, "status": "queued"}

async def process_batch_item(batch_id: str, file_id: str):
    """Process single item in batch"""
    # Implementation similar to process_cv_job but updates batch counters
    pass

@router.get("/health")
async def health_check():
    """Check Ollama connectivity"""
    ollama_ok = await ollama.health_check()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama": "connected" if ollama_ok else "disconnected",
        "message": "Ollama läuft" if ollama_ok else "Ollama nicht erreichbar - bitte Modell prüfen"
    }
