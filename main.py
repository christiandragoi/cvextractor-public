import uuid
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import cors_origins_list
from app.database import engine, Base
from app.routers import (
    candidates,
    config_router,
    extraction,
    identcheck,
    processing,
    review,
    settings as settings_router,
    templates,
)
from app.errors import ApiError, ErrorCode, ErrorStage, new_request_id
import app.models  # ensures Base.metadata populates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified OK")
    except Exception as e:
        logger.error(f"Database init failed (will retry on requests): {e}")
    yield
    await engine.dispose()


app = FastAPI(title="CV Extractor API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, 'request_id', new_request_id())
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.UNEXPECTED_ERROR.value,
                "message": str(exc),
                "stage": "app_internal",
                "request_id": request_id,
                "retryable": False,
                "details": {}
            }
        }
    )


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# App routers
app.include_router(candidates.router, prefix="/api/v1", tags=["candidates"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(extraction.router, prefix="/api", tags=["extraction"])
app.include_router(identcheck.router, prefix="/api/v1", tags=["identcheck"])
app.include_router(review.router, prefix="/api/v1", tags=["review"])
app.include_router(processing.router, prefix="/api/v1/processing", tags=["processing"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(config_router.router, prefix="/api/v1/config", tags=["config"])


# Mount static files
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning("Static directory not found — UI will not be served at root")


@app.get("/")
async def root():
    return {"service": "CV Extractor API", "version": "1.0.0", "docs": "/docs"}
