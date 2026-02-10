"""
Celery configuration for Django project.
Named celery_app.py to avoid conflict with celery package.
"""
import os
from celery import Celery

# Use environment variable or default
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'school_app.settings')

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# Create Celery app with unique name
app = Celery('sms_background_tasks')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, name='debug_task')
def debug_task(self):
    """Debug task to verify Celery is working"""
    return {
        'status': 'success',
        'message': 'Celery is working!',
        'task_id': self.request.id
    }


@app.task(name='health_check')
def health_check():
    """Simple health check task"""
    import datetime
    return {
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat()
    }


app.autodiscover_tasks()

import tasks.student_tasks
import tasks.gaurdian_tasks
import tasks.system_tasks