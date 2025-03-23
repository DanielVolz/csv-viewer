#!/bin/bash

echo "Restarting Celery worker..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec backend bash -c 'pkill -9 -f "celery" && celery -A tasks.tasks worker --loglevel=info -Q search,csv_processing,celery --uid nobody &'

echo "Celery worker restarted."
exit 0
