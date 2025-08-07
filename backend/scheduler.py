import schedule
import time
import logging
from datetime import datetime
from tasks.tasks import morning_reindex

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def trigger_morning_reindex():
    """Trigger the morning reindexing task."""
    try:
        logger.info("Triggering morning reindexing task at 7:00 AM...")
        task = morning_reindex.delay()
        logger.info(f"Morning reindexing task started with ID: {task.id}")
        return task.id
    except Exception as e:
        logger.error(f"Error triggering morning reindexing: {e}")
        return None


def start_scheduler():
    """Start the scheduler for automatic reindexing."""
    logger.info("Starting daily reindexing scheduler...")
    
    # Schedule the morning reindexing at 7:00 AM every day
    schedule.every().day.at("07:00").do(trigger_morning_reindex)
    
    logger.info("Scheduler configured to run reindexing at 7:00 AM daily")
    
    # Keep the scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            time.sleep(60)  # Wait before continuing


if __name__ == "__main__":
    start_scheduler()
