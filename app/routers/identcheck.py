from fastapi import APIRouter

router = APIRouter()

@router.post("/upload")
async def upload_id():
    return {"success": True}
