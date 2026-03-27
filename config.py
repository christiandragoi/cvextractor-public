from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"  # Good for German, or "llama3.1:8b"
    
    # Security
    FIREBASE_PROJECT_ID: str = ""
    APP_CHECK_ENABLED: bool = True
    
    # Processing
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_BATCH_SIZE: int = 5
    PROCESSING_TIMEOUT: int = 120  # seconds
    
    # German compliance
    DATA_RETENTION_HOURS: int = 24  # Auto-delete files after processing
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
