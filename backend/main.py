import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import search, files
from api import stats
from config import settings
from utils.file_watcher import start_file_watcher, stop_file_watcher
import atexit
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for searching and viewing CSV files",
    version="0.1.0"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Include routers
app.include_router(search.router)
app.include_router(files.router)
app.include_router(stats.router)


@app.on_event("startup")
async def startup_event():
    """Start file watcher and trigger full CSV/Stats indexing on application startup."""
    try:
        logger.info("Starting file watcher...")
        start_file_watcher("/app/data")
        logger.info("File watcher started successfully")
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")

    # Indexierung wird über File Watcher oder manuelle API-Calls gestartet
    logger.info("Backend startup completed - indexing will be triggered by file watcher or manual API calls")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop file watcher on application shutdown."""
    try:
        logger.info("Stopping file watcher...")
        stop_file_watcher()
        logger.info("File watcher stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping file watcher: {e}")


# Register cleanup function for unexpected shutdowns
atexit.register(stop_file_watcher)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
