from config import settings

# Broker settings (Redis)
broker_url = settings.REDIS_URL

# Result backend (also Redis)
result_backend = settings.REDIS_URL

# Task routes
task_routes = {
    'tasks.parse_csv': {'queue': 'csv_processing'}
}

# Task serialization format
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Enable UTC
enable_utc = True

# Task result settings
task_track_started = True
task_time_limit = 30 * 60  # 30 minutes
