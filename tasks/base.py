"""
Base task classes - NO CELERY IMPORTS AT MODULE LEVEL
"""
import logging
from celery import Task

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """
    Base class for all Celery background tasks.
    Safe for Celery auto-discovery and worker startup.
    """

    abstract = True  # 🔑 Celery flag (NOT abc.ABC)

    def __init__(self):
        # Celery manages task instances, but this is safe
        self.task_id = None
        self.status = "pending"
        self.progress = 0
        self.message = ""
        super().__init__()

    def run(self, *args, **kwargs):
        """
        Entry point for Celery.
        Subclasses MUST override this.
        """
        raise NotImplementedError("Celery task must implement run()")

    def log_progress(self, message, progress=None):
        """
        Log task progress with visual indicator.
        """
        if progress is not None:
            self.progress = max(0, min(100, int(progress)))

        self.message = message

        bar_length = 20
        filled = int(bar_length * self.progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        log_message = f"[{bar}] {self.progress:3d}% - {message}"
        logger.info(log_message)