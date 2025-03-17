from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tasks.tasks import app as celery_app
from api.files import router as files_router
from api.search import router as search_router

# Make Celery app available to FastAPI
celery = celery_app

app = FastAPI(
    title="CSV Data Viewer",
    description="A FastAPI application for viewing and searching CSV data",
    version="0.1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(files_router)
app.include_router(search_router)


@app.get("/")
async def root():
    """Root endpoint that returns a welcome message."""
    return {
        "message": "Welcome to CSV Data Viewer API",
        "status": "running",
        "version": "0.1.0"
    }
