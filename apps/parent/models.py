"""
Parent Portal models - extending existing Guardian model
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class ParentNotification(models.Model):
    """Notifications for parents"""
    guardian = models.ForeignKey(
        'students.Guardian',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('academic', 'Academic'),
            ('fee', 'Fee Payment'),
            ('attendance', 'Attendance'),
            ('announcement', 'Announcement'),
            ('system', 'System'),
        ],
        default='announcement'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.guardian} - {self.title}"

class ParentLoginLog(models.Model):
    """Log parent portal logins"""
    guardian = models.ForeignKey(
        'students.Guardian',
        on_delete=models.CASCADE,
        related_name='login_logs'
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.guardian} - {self.login_time}"

class StudentProgress(models.Model):
    """Track student progress for parent viewing"""
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='progress_reports'
    )
    term = models.ForeignKey('corecode.AcademicTerm', on_delete=models.CASCADE)
    average_score = models.DecimalField(max_digits=5, decimal_places=2)
    position_in_class = models.IntegerField(null=True, blank=True)
    total_students = models.IntegerField()
    teacher_comment = models.TextField(blank=True)
    principal_comment = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-generated_at']
        unique_together = ['student', 'term']
    
    def __str__(self):
        return f"{self.student} - {self.term}"