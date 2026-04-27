from fastapi import APIRouter

router = APIRouter()

@router.get("/providers")
async def list_providers():
    return [
        {
            "id": "demo",
            "display_name": "Demo Extractor (No API Key)",
            "provider_type": "DEMO",
            "model_selected": "demo",
            "is_active": True,
            "is_validated": True,
            "api_key_hint": "",
        }
    ]

@router.get("/system")
async def list_system_settings():
    return []
