"""
System-level background tasks.

This module contains low-level, cross-cutting background tasks that support
the overall stability and maintenance of the system. These tasks are not tied
to a specific domain model (students, guardians, staff) and should remain
lightweight, predictable, and safe to retry.

Design principles:
- Explicit task names for Celery stability
- Controlled retries (no retry storms)
- Loud logging, quiet failures where appropriate
- No dependency on custom Celery base classes
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger("system.tasks")


# ---------------------------------------------------------------------------
# SYSTEM ALERT TASK
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="system.send_alert",
    autoretry_for=(Exception,),
    retry_backoff=300,          # 5 minutes base backoff
    retry_backoff_max=1800,     # max 30 minutes
    retry_kwargs={"max_retries": 3},
)
def send_system_alert_task(
    self,
    alert_type: str,
    sender: str | None = None,
    instance_id: str | None = None,
    error: str | None = None,
):
    """
    Send a system-level alert email to site administrators.

    This task is intended for:
    - Critical background task failures
    - Data corruption warnings
    - Unexpected system states

    The task retries automatically on failure with exponential backoff.
    Failures are logged clearly to avoid silent system degradation.
    """
    task_id = self.request.id
    timestamp = timezone.now()

    logger.info(
        "[%s] Preparing system alert",
        task_id,
        extra={
            "alert_type": alert_type,
            "sender": sender,
            "instance_id": instance_id,
        },
    )

    school_name = getattr(settings, "SCHOOL_NAME", "School System")
    site_url = getattr(settings, "SITE_URL", "N/A")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

    admins = getattr(settings, "ADMINS", [])
    admin_emails = [email for _, email in admins if email]

    if not admin_emails:
        logger.warning(
            "[%s] No ADMINS configured; system alert will not be emailed",
            task_id,
        )
        return {
            "success": False,
            "reason": "no_admin_emails",
            "alert_type": alert_type,
        }

    subject = f"[{school_name}] System Alert: {alert_type}"

    message = f"""
SYSTEM ALERT

Type: {alert_type}
Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Sender: {sender or 'Unknown'}
Instance ID: {instance_id or 'N/A'}

Error Details:
{error or 'No error details provided'}

Environment: {"Development" if settings.DEBUG else "Production"}
Site URL: {site_url}

This message was generated automatically by the system task runner.
"""

    send_mail(
        subject=subject,
        message=message.strip(),
        from_email=from_email,
        recipient_list=admin_emails,
        fail_silently=False,
    )

    logger.info(
        "[%s] System alert sent successfully",
        task_id,
        extra={
            "alert_type": alert_type,
            "recipients": len(admin_emails),
        },
    )

    return {
        "success": True,
        "alert_type": alert_type,
        "sent_to": admin_emails,
        "sent_at": timestamp.isoformat(),
    }


# ---------------------------------------------------------------------------
# CLEANUP TASK
# ---------------------------------------------------------------------------

@shared_task(
    name="system.cleanup_old_files",
    autoretry_for=(Exception,),
    retry_backoff=600,          # 10 minutes
    retry_kwargs={"max_retries": 2},
)
def cleanup_old_files_task(days_old: int = 30):
    """
    Clean up old system records and temporary data.

    Currently cleans:
    - StudentBulkUpload records older than `days_old`

    This task is intentionally conservative:
    - No hard deletes without logging
    - No silent failures
    - Limited retries
    """
    logger.info(
        "Starting system cleanup",
        extra={"days_old": days_old},
    )

    try:
        from apps.students.models import StudentBulkUpload
    except ImportError as exc:
        logger.critical(
            "Cleanup aborted: required model import failed",
            exc_info=exc,
        )
        raise

    cutoff_date = timezone.now() - timedelta(days=days_old)

    logger.debug(
        "Calculated cleanup cutoff date",
        extra={"cutoff_date": cutoff_date.isoformat()},
    )

    queryset = StudentBulkUpload.objects.filter(
        date_uploaded__lt=cutoff_date
    )

    total = queryset.count()

    if total == 0:
        logger.info("No old records found for cleanup")
        return {
            "success": True,
            "cleaned": 0,
            "days_old": days_old,
        }

    logger.warning(
        "Deleting old StudentBulkUpload records",
        extra={"count": total},
    )

    deleted_count, _ = queryset.delete()

    logger.info(
        "Cleanup completed successfully",
        extra={
            "requested_days_old": days_old,
            "deleted_records": deleted_count,
        },
    )

    return {
        "success": True,
        "cleaned": deleted_count,
        "days_old": days_old,
        "cutoff_date": cutoff_date.isoformat(),
    }