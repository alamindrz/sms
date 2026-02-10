"""
Signals for the students app with transaction safety.
All heavy operations are offloaded to Celery with proper transaction handling.
"""
import os
import logging
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


# ==================== SAFE FILE CLEANUP ====================

def safe_delete_file(file_field):
    """
    Safely delete a file with error handling.
    Only deletes if file exists in storage.
    """
    if file_field and file_field.name:
        try:
            if default_storage.exists(file_field.name):
                default_storage.delete(file_field.name)
                logger.debug(f"Deleted file: {file_field.name}")
            else:
                logger.warning(f"File not found in storage: {file_field.name}")
        except Exception as e:
            logger.error(f"Error deleting file {file_field.name}: {str(e)}")


@receiver(post_delete)
def safe_delete_files_on_delete(sender, instance, **kwargs):
    """
    Safely delete files when models are deleted.
    Runs AFTER transaction commit to avoid orphaned files.
    """
    # Only handle specific models
    if sender.__name__ in ['StudentBulkUpload', 'Student', 'Guardian']:
        try:
            # Schedule file deletion after transaction
            transaction.on_commit(lambda: _process_file_deletion(sender, instance))
        except Exception as e:
            logger.error(f"Error scheduling file deletion: {str(e)}")


def _process_file_deletion(sender, instance):
    """
    Process file deletion after transaction commit.
    """
    try:
        if sender.__name__ == 'StudentBulkUpload':
            if hasattr(instance, 'csv_file') and instance.csv_file:
                safe_delete_file(instance.csv_file)
                
        elif sender.__name__ == 'Student':
            if hasattr(instance, 'passport') and instance.passport:
                safe_delete_file(instance.passport)
                
        elif sender.__name__ == 'Guardian':
            if hasattr(instance, 'photo') and instance.photo:
                safe_delete_file(instance.photo)
                
    except Exception as e:
        logger.error(f"Error in file deletion processing: {str(e)}")


# ==================== STUDENT BULK UPLOAD SIGNALS ====================

@receiver(post_save, sender='students.StudentBulkUpload')
def trigger_student_bulk_import(sender, instance, created, **kwargs):
    """
    Trigger background import when CSV is uploaded.
    Uses transaction.on_commit to avoid race conditions.
    """
    if created and instance.csv_file:
        try:
            # Import inside to avoid circular imports
            from tasks.student_tasks import import_students_from_csv
            
            logger.info(f"📥 CSV upload detected: {instance.csv_file.name} (ID: {instance.id})")
            
            # Schedule task AFTER transaction commit
            transaction.on_commit(
                lambda: _queue_import_task(instance)
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to schedule import task: {str(e)}")
            # Update status immediately (in same transaction)
            instance.task_status = 'failed'
            instance.error_message = str(e)[:500]
            instance.save(update_fields=['task_status', 'error_message'])


def _queue_import_task(instance):
    """
    Queue the import task after transaction commit.
    """
    try:
        from tasks.student_tasks import import_students_from_csv
        
        task = import_students_from_csv.delay(instance.id)
        
        # Update instance with task ID (needs fresh query)
        from apps.students.models import StudentBulkUpload
        with transaction.atomic():
            fresh_instance = StudentBulkUpload.objects.select_for_update().get(id=instance.id)
            fresh_instance.task_id = task.id
            fresh_instance.save(update_fields=['task_id'])
        
        logger.info(f"✅ Import task queued: {task.id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to queue import task: {str(e)}")


# ==================== GUARDIAN SIGNALS ====================

@receiver(post_save, sender='students.Guardian')
def trigger_guardian_user_creation(sender, instance, created, **kwargs):
    """
    Create user account for new guardian in background.
    Uses transaction.on_commit for safety.
    """
    if created and instance.email and not instance.user:
        try:
            from tasks.guardian_tasks import create_guardian_user_account
            
            logger.info(f"👤 New guardian created: {instance.email} (ID: {instance.id})")
            
            # Schedule task AFTER transaction commit
            transaction.on_commit(
                lambda: _queue_guardian_user_task(instance)
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to schedule guardian user task: {str(e)}")
            # Update status
            instance.user_creation_status = 'failed'
            instance.save(update_fields=['user_creation_status'])


def _queue_guardian_user_task(instance):
    """
    Queue guardian user creation task after transaction commit.
    """
    try:
        from tasks.guardian_tasks import create_guardian_user_account
        
        task = create_guardian_user_account.delay(instance.id)
        
        # Update instance with task ID
        from apps.students.models import Guardian
        with transaction.atomic():
            fresh_instance = Guardian.objects.select_for_update().get(id=instance.id)
            fresh_instance.user_creation_task_id = task.id
            fresh_instance.save(update_fields=['user_creation_task_id'])
        
        logger.info(f"✅ Guardian user task queued: {task.id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to queue guardian user task: {str(e)}")


# ==================== ERROR HANDLING SIGNAL ====================

@receiver(post_save)
def log_model_changes_for_auditing(sender, instance, created, **kwargs):
    """
    Log important model changes for auditing.
    Lightweight - runs synchronously.
    """
    # Only log specific models
    important_models = ['Student', 'Guardian', 'StudentBulkUpload', 'PromotionLog']
    
    if sender.__name__ in important_models:
        action = "created" if created else "updated"
        
        # Get identifier
        identifier = getattr(instance, 'id', 'N/A')
        if hasattr(instance, 'email'):
            identifier = instance.email
        elif hasattr(instance, 'student_number'):
            identifier = instance.student_number
        
        logger.debug(f"📝 {sender.__name__} {action}: {identifier}")
        
        # Log specific field changes for updates
        if not created and hasattr(instance, 'tracker'):
            try:
                changed_fields = instance.tracker.changed()
                if changed_fields:
                    logger.debug(f"   Changed fields: {', '.join(changed_fields)}")
            except AttributeError:
                pass