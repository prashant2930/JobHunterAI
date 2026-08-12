import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.health import router as health_router
from app.api.profile import router as profile_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router

# Set up logging configuration
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jobhunter")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the local SQLite database
    logger.info("Initializing SQLite database on startup...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
    yield
    # Shutdown: Close resources if any
    logger.info("Shutting down JobHunter AI backend...")

app = FastAPI(
    title="JobHunter AI Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to allow local web panel integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers under the /api namespace
app.include_router(health_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(matches_router, prefix="/api")

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception caught on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )
