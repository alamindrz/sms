"""
Configuration for background tasks - NO EARLY DJANGO IMPORTS
"""
import os
import logging

logger = logging.getLogger(__name__)

# Use explicit environment variable for CPanel detection
ENV_TYPE = os.environ.get('ENV_TYPE', 'STANDARD').upper()
IS_CPANEL = ENV_TYPE == 'CPANEL'

# Broker configuration - prioritize environment variables
BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'django-db')

# Task configuration
TASK_CONFIG = {
    'USE_CELERY': not IS_CPANEL,  # Use Celery by default unless CPanel
    'IS_CPANEL': IS_CPANEL,
    'ENV_TYPE': ENV_TYPE,
    'BROKER_URL': BROKER_URL,
    'RESULT_BACKEND': RESULT_BACKEND,
    'TASK_TRACK_STARTED': True,
    'TASK_TIME_LIMIT': 30 * 60,
    'WORKER_CONCURRENCY': int(os.environ.get('CELERY_WORKER_CONCURRENCY', 4)),
    'TASK_SERIALIZER': 'json',
    'RESULT_SERIALIZER': 'json',
    'ACCEPT_CONTENT': ['json'],
    'TIMEZONE': 'UTC',
}

# Log the configuration
logger.info(f"Celery Configuration:")
logger.info(f"  Environment: {ENV_TYPE}")
logger.info(f"  Broker URL: {BROKER_URL}")
logger.info(f"  Result Backend: {RESULT_BACKEND}")
