"""
Student-related background tasks.

Design goals:
- Memory-safe (streamed CSV, bounded batches)
- Transaction-safe (short atomic sections)
- Celery-correct (idempotent, retry-aware)
- Observable (clear logs, progress updates, failure capture)

All tasks in this file are SAFE to retry unless otherwise stated.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Iterable, List

from celery import shared_task
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BATCH_SIZE = 100
MAX_ROWS_PER_TASK = 10_000
FAILED_ROWS_CACHE_TTL = 60 * 60  # seconds


# =====================================================================
# STUDENT CSV IMPORT
# =====================================================================

@shared_task(
    bind=True,
    name="students.import_from_csv",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def import_students_from_csv(self, bulk_upload_id: int) -> dict:
    """
    Entry-point Celery task.

    High-level orchestration only:
    - Locks upload row
    - Marks task state
    - Delegates heavy work
    - Finalizes status

    Any unhandled exception = task FAILURE (intentional).
    """
    from apps.students.models import StudentBulkUpload

    task_id = self.request.id
    logger.info("[%s] Student CSV import requested (upload_id=%s)", task_id, bulk_upload_id)

    try:
        with transaction.atomic():
            upload = (
                StudentBulkUpload.objects
                .select_for_update()
                .get(id=bulk_upload_id)
            )

            if upload.task_status in {"processing", "completed"}:
                logger.warning("[%s] Upload already %s", task_id, upload.task_status)
                return {"status": upload.task_status}

            upload.task_id = task_id
            upload.task_status = "processing"
            upload.processing_started = timezone.now()
            upload.current_status_message = "Starting import"
            upload.progress_percentage = 0
            upload.save()

        stats = _process_csv_stream(upload)

        with transaction.atomic():
            upload.refresh_from_db()
            upload.task_status = "completed"
            upload.processing_completed = timezone.now()
            upload.progress_percentage = 100
            upload.current_status_message = (
                f"Completed: {stats['created']} created, "
                f"{stats['failed']} failed"
            )
            upload.save()

        logger.info("[%s] Import completed successfully", task_id)
        return {"status": "completed", **stats}

    except StudentBulkUpload.DoesNotExist:
        logger.error("[%s] Upload not found (id=%s)", task_id, bulk_upload_id)
        return {"status": "missing"}

    except Exception as exc:
        logger.exception("[%s] Import crashed", task_id)

        # Best-effort failure update (never mask original error)
        StudentBulkUpload.objects.filter(id=bulk_upload_id).update(
            task_status="failed",
            error_message=str(exc)[:500],
            processing_completed=timezone.now(),
        )
        raise


# =====================================================================
# CSV STREAM PROCESSOR
# =====================================================================


def _process_csv_stream(upload) -> dict:
    """
    Stream and import students from a CSV file safely.

    Guarantees:
    - No long-running DB transaction
    - No unbounded memory usage
    - Storage-backend agnostic (text or binary)
    - CSV module always receives TEXT (never bytes)
    - Partial failures do not crash the task
    """
    
    # Local imports to avoid circular dependency
    from apps.students.models import Student, StudentBulkUpload
    from apps.corecode.models import StudentClass
    
    # Initialize counters and caches
    created: int = 0
    failed: int = 0
    total: int = 0

    failed_rows: List[dict] = []
    batch: List[Student] = []
    class_cache: dict[str, StudentClass] = {}

    logger.info(
        "Starting CSV stream processing (upload_id=%s)",
        upload.id,
    )

    # ------------------------------------------------------------------
    # Open CSV safely (Binary Mode + Sniffer)
    # ------------------------------------------------------------------

    # 1. Force binary mode to prevent TypeError in TextIOWrapper
    upload.csv_file.open('rb')
    raw_file = upload.csv_file.file

    # 2. Wrap in TextIOWrapper to handle encoding safely
    text_stream = io.TextIOWrapper(
        raw_file,
        encoding="utf-8-sig",
        newline="",
    )

    try:
        # 3. Sniff the dialect (detect delimiter like ; or ,)
        # Read a small sample to detect format
        sample = text_stream.read(2048)
        text_stream.seek(0)
        
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            # Fallback to standard Excel (comma) if sniffing fails
            dialect = 'excel'

        # 4. Initialize Reader with detected dialect
        reader = csv.DictReader(text_stream, dialect=dialect)

        # 5. Normalize headers (fix case sensitivity and whitespace)
        # e.g., "Registration Number " -> "registration_number"
        if reader.fieldnames:
            reader.fieldnames = [
                name.strip().lower().replace(' ', '_') 
                for name in reader.fieldnames
            ]

        # Validate required fields
        required_fields = {"registration_number", "surname", "firstname"}
        fieldnames = reader.fieldnames or []

        if not required_fields.issubset(fieldnames):
            missing = required_fields - set(fieldnames)
            raise ValueError(f"Missing required CSV fields: {missing}")

        # ------------------------------------------------------------------
        # Row processing loop
        # ------------------------------------------------------------------

        for row_number, row in enumerate(reader, start=1):
            total += 1

            if total > MAX_ROWS_PER_TASK:
                logger.warning(
                    "Row limit reached (%s); stopping import",
                    MAX_ROWS_PER_TASK,
                )
                break

            try:
                # Use the existing helper to build student object
                student = _build_student(row, class_cache)
                batch.append(student)

                # Flush batch if full
                if len(batch) >= BATCH_SIZE:
                    created += _flush_batch(batch)
                    batch.clear()

            except Exception as exc:
                failed += 1
                failed_rows.append({
                    "row": row_number,
                    "error": str(exc),
                })

            # Progress update every 100 rows
            if row_number % 100 == 0:
                StudentBulkUpload.objects.filter(
                    id=upload.id,
                    task_status="processing",
                ).update(
                    records_processed=row_number,
                    records_created=created,
                    records_failed=failed,
                    progress_percentage=min(
                        int((row_number / MAX_ROWS_PER_TASK) * 100),
                        99,
                    ),
                    current_status_message=f"Processed {row_number} rows…",
                )

        # ------------------------------------------------------------------
        # Flush remainder
        # ------------------------------------------------------------------

        if batch:
            created += _flush_batch(batch)

        # ------------------------------------------------------------------
        # Final persistence
        # ------------------------------------------------------------------

        StudentBulkUpload.objects.filter(id=upload.id).update(
            total_records=total,
            records_created=created,
            records_failed=failed,
        )

        if failed_rows:
            cache.set(
                f"student_import_failures_{upload.id}",
                failed_rows,
                FAILED_ROWS_CACHE_TTL,
            )

        logger.info(
            "CSV import finished (upload_id=%s total=%s created=%s failed=%s)",
            upload.id,
            total,
            created,
            failed,
        )

        return {
            "total": total,
            "created": created,
            "failed": failed,
        }

    finally:
        # ------------------------------------------------------------------
        # Always close streams cleanly
        # ------------------------------------------------------------------
        try:
            if hasattr(text_stream, "detach"):
                text_stream.detach()
        except Exception:
            pass

        try:
            upload.csv_file.close()
        except Exception:
            pass



# =====================================================================
# HELPERS
# =====================================================================

def _build_student(row: dict, class_cache: dict):
    """
    Validate and build a Student instance (not saved).
    """
    from apps.students.models import Student
    from apps.corecode.models import StudentClass

    reg = row.get("registration_number", "").strip()
    if not reg:
        raise ValueError("Missing registration number")

    if Student.objects.filter(registration_number=reg).exists():
        raise ValueError("Duplicate registration number")

    class_name = row.get("current_class", "").strip()
    student_class = None

    if class_name:
        student_class = class_cache.get(class_name)
        if not student_class:
            student_class, _ = StudentClass.objects.get_or_create(name=class_name)
            class_cache[class_name] = student_class

    return Student(
        registration_number=reg,
        surname=row.get("surname", "").strip(),
        firstname=row.get("firstname", "").strip(),
        other_name=row.get("other_names", "").strip(),
        gender=row.get("gender", "").strip().lower()[:10],
        parent_mobile_number=row.get("parent_number", "").strip(),
        address=row.get("address", "").strip(),
        current_class=student_class,
        current_status="active",
    )


def _flush_batch(batch: Iterable) -> int:
    """
    Insert a batch safely.

    IMPORTANT:
    - No ignore_conflicts (we want real failures)
    - Short transaction
    """
    from apps.students.models import Student

    try:
        with transaction.atomic():
            Student.objects.bulk_create(batch)
        logger.info("Inserted %s students", len(batch))
        return len(batch)

    except IntegrityError as exc:
        logger.exception("Batch insert failed")
        raise exc


def _update_progress(upload, processed, created, failed):
    """
    Cheap progress update (no locking).
    """
    upload.records_processed = processed
    upload.records_created = created
    upload.records_failed = failed
    upload.progress_percentage = min(
        int((processed / MAX_ROWS_PER_TASK) * 100), 99
    )
    upload.current_status_message = f"Processed {processed} rows"
    upload.save(update_fields=[
        "records_processed",
        "records_created",
        "records_failed",
        "progress_percentage",
        "current_status_message",
    ])


# =====================================================================
# BULK STATUS UPDATE
# =====================================================================

@shared_task(name="students.bulk_update_status")
def bulk_update_student_status(student_ids: list[int], new_status: str) -> dict:
    """
    Update student status in small transactional chunks.
    """
    from apps.students.models import Student

    updated = 0

    for i in range(0, len(student_ids), 50):
        with transaction.atomic():
            updated += Student.objects.filter(
                id__in=student_ids[i:i + 50]
            ).update(
                status=new_status,
                updated_at=timezone.now(),
            )

    logger.info("Updated %s students → %s", updated, new_status)
    return {"updated": updated}


# =====================================================================
# PROMOTION TASK
# =====================================================================

@shared_task(name="students.process_promotion_batch")
def process_promotion_batch(payload: dict) -> dict:
    """
    Promote students from one class to another.

    Failures are isolated per student.
    """
    from apps.students.models import Student, PromotionLog
    from apps.corecode.models import StudentClass, AcademicSession

    students = payload.get("student_ids", [])
    from_class = StudentClass.objects.get(id=payload["from_class_id"])
    to_class = StudentClass.objects.get(id=payload["to_class_id"])
    session = AcademicSession.objects.get(id=payload["session_id"])
    promoted_by = payload.get("promoted_by_id")

    promoted = failed = 0

    for i in range(0, len(students), 20):
        with transaction.atomic():
            for student_id in students[i:i + 20]:
                try:
                    student = Student.objects.select_for_update().get(id=student_id)

                    if student.current_class_id != from_class.id:
                        raise ValueError("Class mismatch")

                    student.current_class = to_class
                    student.save(update_fields=["current_class", "updated_at"])

                    PromotionLog.objects.create(
                        student=student,
                        from_class=from_class,
                        to_class=to_class,
                        session=session,
                        promoted_by_id=promoted_by,
                    )
                    promoted += 1

                except Exception:
                    failed += 1

    logger.info("Promotion finished (promoted=%s failed=%s)", promoted, failed)
    return {"promoted": promoted, "failed": failed}