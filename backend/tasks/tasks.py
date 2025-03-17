from celery import Celery
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery('csv_viewer')

# Load Celery configuration
app.config_from_object('celeryconfig')


@app.task(name='tasks.parse_csv')
def parse_csv(file_path: str) -> dict:
    """
    Task to parse a CSV file.
    This is currently a stub that just logs the file path.
    
    Args:
        file_path: Path to the CSV file to parse
        
    Returns:
        dict: A dictionary containing the parsing result
    """
    logger.info(f"Stub: Processing CSV file at {file_path}")
    return {
        "status": "success",
        "message": f"Stub: Successfully processed {file_path}",
        "file_path": file_path
    }
