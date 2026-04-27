import uuid
from enum import Enum
from fastapi import HTTPException

class ErrorCode(Enum):
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"

class ErrorStage(Enum):
    LLM_INFERENCE = "llm_inference"
    TEMPLATE_POPULATION = "template_population"
    STORAGE = "storage"
    DATABASE = "database"

class ApiError(HTTPException):
    def __init__(self, status_code: int, code: ErrorCode, message: str, stage: ErrorStage = None, request_id: str = None, retryable: bool = False):
        self.code = code
        self.stage = stage
        self.request_id = request_id or new_request_id()
        self.retryable = retryable
        detail = {
            "error": {
                "code": code.value,
                "message": message,
                "stage": stage.value if stage else "unknown",
                "request_id": self.request_id,
                "retryable": retryable,
                "details": {}
            }
        }
        super().__init__(status_code=status_code, detail=detail)

def new_request_id():
    return str(uuid.uuid4())
