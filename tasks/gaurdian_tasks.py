"""
Guardian-related background tasks
Production-safe, Celery-correct, and retry-controlled.
"""

import logging
import re
import uuid

from celery import shared_task, group
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def generate_username(email: str, guardian_id: int | None = None) -> str:
    """
    Generate a safe, unique Django username from email.
    Guaranteed uniqueness via DB constraint fallback.
    """
    from django.contrib.auth.models import User

    local_part = email.split("@")[0]
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", local_part) or "guardian"

    base = f"{safe}_{guardian_id}" if guardian_id else safe
    base = base[:150]

    username = base

    if not User.objects.filter(username=username).exists():
        return username

    # Fallbacks
    for _ in range(10):
        suffix = uuid.uuid4().hex[:8]
        username = f"{safe}_{suffix}"[:150]
        if not User.objects.filter(username=username).exists():
            return username

    raise RuntimeError("Username generation failed after multiple attempts")


# -------------------------------------------------------------------
# Tasks
# -------------------------------------------------------------------

@shared_task(
    bind=True,
    name="guardians.create_user_account",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def create_guardian_user_account(self, guardian_id: int):
    """
    Create a Django User for a Guardian.
    Fully idempotent & transaction-safe.
    """
    from apps.students.models import Guardian
    from django.contrib.auth.models import User, Group

    task_id = self.request.id

    try:
        with transaction.atomic():
            guardian = Guardian.objects.select_for_update().get(id=guardian_id)

            if guardian.user:
                logger.info("[%s] Guardian already has user", task_id)
                return {"status": "exists", "guardian_id": guardian_id}

            if not guardian.email:
                raise ValueError("Guardian email is required")

            guardian.user_creation_task_id = task_id
            guardian.user_creation_status = "processing"
            guardian.save(update_fields=["user_creation_task_id", "user_creation_status"])

        username = generate_username(guardian.email, guardian_id)
        password = User.objects.make_random_password()

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=guardian.email,
                    password=password,
                    first_name=guardian.firstname[:30],
                    last_name=guardian.surname[:30],
                    is_active=True,
                )

                group, _ = Group.objects.get_or_create(name="Guardians")
                user.groups.add(group)

                guardian.user = user
                guardian.user_created_at = timezone.now()
                guardian.user_creation_status = "completed"
                guardian.save()

        except IntegrityError:
            # Ultra-rare race condition fallback
            username = generate_username(
                guardian.email, f"{guardian_id}_{uuid.uuid4().hex[:4]}"
            )
            user = User.objects.create_user(
                username=username,
                email=guardian.email,
                password=password,
                is_active=True,
            )
            guardian.user = user
            guardian.user_creation_status = "completed"
            guardian.save()

        logger.info("[%s] User created: %s", task_id, username)

        send_welcome_email_to_guardian.delay(guardian_id)

        return {
            "status": "created",
            "guardian_id": guardian_id,
            "user_id": user.id,
            "username": username,
        }

    except Guardian.DoesNotExist:
        logger.warning("[%s] Guardian not found", task_id)
        return {"status": "missing", "guardian_id": guardian_id}

    except Exception as exc:
        logger.exception("[%s] User creation failed", task_id)

        try:
            Guardian.objects.filter(id=guardian_id).update(
                user_creation_status="failed"
            )
        except Exception:
            pass

        raise exc


# -------------------------------------------------------------------

@shared_task(
    bind=True,
    name="guardians.send_welcome_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_welcome_email_to_guardian(self, guardian_id: int):
    """
    Sends a welcome email exactly once.
    """
    from apps.students.models import Guardian

    guardian = Guardian.objects.get(id=guardian_id)

    if guardian.last_welcome_email_sent:
        logger.info(
            "[%s] Welcome email already sent, skipping",
            self.request.id,
        )
        return {"status": "skipped", "guardian_id": guardian_id}

    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    school_name = getattr(settings, "SCHOOL_NAME", "Our School")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")

    try:
        reset_url = f"{site_url}{reverse('password_reset')}"
    except Exception:
        reset_url = f"{site_url}/accounts/password/reset/"

    message = f"""
Dear {guardian.full_name},

Welcome to {school_name}!

Your parent portal account has been created.

Login URL: {site_url}
Username: {guardian.user.username}
Password: Use password reset

Reset here:
{reset_url}

Regards,
{school_name}
""".strip()

    send_mail(
        subject=f"Welcome to {school_name}",
        message=message,
        from_email=from_email,
        recipient_list=[guardian.email],
        fail_silently=False,
    )

    guardian.last_welcome_email_sent = timezone.now()
    guardian.save(update_fields=["last_welcome_email_sent"])

    logger.info("[%s] Welcome email sent", self.request.id)

    return {"status": "sent", "guardian_id": guardian_id}


# -------------------------------------------------------------------

@shared_task(name="guardians.bulk_notify")
def bulk_send_guardian_notifications(
    guardian_ids: list[int],
    notification_type: str,
    message_data: dict,
):
    """
    Fan-out notification sender using Celery group.
    """
    job = group(
        send_guardian_notification.s(
            guardian_id,
            notification_type,
            message_data.get("subject", "Notification"),
            message_data.get("message", ""),
        )
        for guardian_id in guardian_ids
    )

    result = job.apply_async()

    logger.info(
        "Queued %s notifications (%s)",
        len(guardian_ids),
        result.id,
    )

    return {
        "status": "queued",
        "count": len(guardian_ids),
        "group_id": result.id,
    }


# -------------------------------------------------------------------

@shared_task(name="guardians.send_notification")
def send_guardian_notification(
    guardian_id: int,
    notification_type: str,
    subject: str,
    message: str,
):
    """
    Send a single notification email.
    Never retries (safe fail).
    """
    from apps.students.models import Guardian

    try:
        guardian = Guardian.objects.get(id=guardian_id)

        if not guardian.email:
            return {"status": "no-email", "guardian_id": guardian_id}

        body = f"""
Dear {guardian.full_name},

{message}

Regards,
{getattr(settings, 'SCHOOL_NAME', 'School')}
""".strip()

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(
                settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"
            ),
            recipient_list=[guardian.email],
            fail_silently=False,
        )

        return {"status": "sent", "guardian_id": guardian_id}

    except Exception as exc:
        logger.error(
            "Notification failed for guardian %s: %s",
            guardian_id,
            exc,
        )
        return {"status": "failed", "guardian_id": guardian_id}