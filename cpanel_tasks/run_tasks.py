#!/usr/bin/env python
"""
CPanel task runner - executes tasks synchronously when Celery is not available
"""
import os
import sys
import django
import logging
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_app.settings')
django.setup()

from tasks.student_tasks import import_students_task, bulk_update_students_task
from tasks.guardian_tasks import create_guardian_user_task, send_welcome_email_task

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def run_import_students(bulk_upload_id):
    """Run student import task"""
    logger.info(f"Running student import for upload ID: {bulk_upload_id}")
    return import_students_task(bulk_upload_id)


def run_create_guardian_user(guardian_id):
    """Run guardian user creation task"""
    logger.info(f"Creating user for guardian ID: {guardian_id}")
    return create_guardian_user_task(guardian_id)


if __name__ == "__main__":
    # This script can be called from CPanel cron jobs
    # Example: python cpanel_tasks/run_tasks.py import_students 123
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'import_students' and len(sys.argv) > 2:
            result = run_import_students(int(sys.argv[2]))
            print(f"Result: {result}")
        
        elif command == 'create_guardian_user' and len(sys.argv) > 2:
            result = run_create_guardian_user(int(sys.argv[2]))
            print(f"Result: {result}")
        
        else:
            print("Unknown command. Available commands:")
            print("  import_students <upload_id>")
            print("  create_guardian_user <guardian_id>")
    else:
        print("No command specified")