import os
from pathlib import Path

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "./storage"))
UPLOADS_DIR = STORAGE_ROOT / "uploads"
OUTPUT_DIR = STORAGE_ROOT / "output"
TEMPLATES_DIR = STORAGE_ROOT / "templates"
cors_origins_str = os.environ.get("CORS_ORIGINS", "*")
cors_origins_list = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
if not cors_origins_list:
    cors_origins_list = ["*"]
