import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import search, files
from api import stats
from config import settings
from utils.file_watcher import start_file_watcher, stop_file_watcher
import atexit
import logging
import asyncio
import os

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
    """Start file watcher on application startup."""
    # Allow tests and CI to disable background tasks for speed/stability
    if os.environ.get("DISABLE_STARTUP_TASKS") == "1":
        logger.info("Startup tasks disabled by DISABLE_STARTUP_TASKS=1 (tests/CI mode)")
        return
    try:
        logger.info("Starting file watcher...")
        start_file_watcher("/app/data")
        logger.info("File watcher started successfully")
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")

    # In the background: wait for OpenSearch, then backfill stats snapshots if missing
    async def _maybe_backfill_snapshots():
        try:
            from utils.opensearch import opensearch_config
            client = opensearch_config.client
            # Wait until OpenSearch responds to ping (max ~30s)
            ready = False
            for _ in range(10):
                try:
                    if client.ping():
                        ready = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(3)
            if not ready:
                logger.warning("OpenSearch not ready within startup window; skipping auto backfill.")
                return

            need_stats = False
            need_loc = False
            try:
                if not client.indices.exists(index=opensearch_config.stats_index):
                    need_stats = True
                else:
                    cnt = client.count(index=opensearch_config.stats_index).get('count', 0)
                    # Heuristic: if too few docs (< 10), consider empty and backfill
                    if cnt < 10:
                        need_stats = True
            except Exception:
                need_stats = True

            try:
                if not client.indices.exists(index=opensearch_config.stats_loc_index):
                    need_loc = True
                else:
                    cnt2 = client.count(index=opensearch_config.stats_loc_index).get('count', 0)
                    if cnt2 < 10:
                        need_loc = True
            except Exception:
                need_loc = True

            if need_stats or need_loc:
                logger.info(f"Scheduling snapshot backfill: stats={need_stats}, loc={need_loc}")
                try:
                    from tasks.tasks import backfill_stats_snapshots, backfill_location_snapshots
                    if need_stats:
                        backfill_stats_snapshots.delay("/app/data")
                    if need_loc:
                        backfill_location_snapshots.delay("/app/data")
                except Exception as e:
                    logger.error(f"Failed to start backfill tasks: {e}")
            else:
                logger.info("Snapshot indices look populated; no backfill needed.")
        except Exception as e:
            logger.error(f"Auto-backfill probe failed: {e}")

    # Fire and forget
    try:
        asyncio.create_task(_maybe_backfill_snapshots())
    except Exception as e:
        logger.debug(f"Could not schedule auto-backfill task: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop file watcher on application shutdown."""
    if os.environ.get("DISABLE_STARTUP_TASKS") == "1":
        logger.info("Shutdown tasks disabled by DISABLE_STARTUP_TASKS=1 (tests/CI mode)")
        return
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
