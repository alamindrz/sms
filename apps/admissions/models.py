from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.corecode.models import AcademicSession, StudentClass
from apps.students.models import Student
from apps.staffs.models import Staff
import re
import uuid

class AdmissionApplication(models.Model):
    """Model for admission applications (prospective students)"""
    
    class ApplicationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        UNDER_REVIEW = 'under_review', _('Under Review')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        WAITLISTED = 'waitlisted', _('Waitlisted')
        ACCEPTED = 'accepted', _('Accepted by Guardian')  # New status
    
    # Application Info
    application_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text=_("Auto-generated application number")
    )
    application_date = models.DateField(default=timezone.now)
    admission_session = models.ForeignKey(
        'corecode.AcademicSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admission_applications'
    )
    admission_class = models.ForeignKey(
        'corecode.StudentClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admission_applications'
    )
    
    # Guardian Information (Financial/Legal Representative)
    guardian_name = models.CharField(max_length=200)
    guardian_email = models.EmailField()
    guardian_phone = models.CharField(max_length=20)
    guardian_address = models.TextField()
    guardian_relationship = models.CharField(
        max_length=50,
        default='Parent',
        choices=[
            ('Parent', 'Parent'),
            ('Sibling', 'Sibling'),
            ('Relative', 'Relative'),
            ('Guardian', 'Legal Guardian'),
            ('Other', 'Other'),
        ]
    )
    guardian_photo = models.ImageField(
        upload_to='admissions/guardians/',
        null=True,
        blank=True
    )
    
    # Student Bio-data
    first_name = models.CharField(max_length=200)
    middle_name = models.CharField(max_length=200, blank=True)
    surname = models.CharField(max_length=200)
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female')]
    )
    date_of_birth = models.DateField()
    birth_certificate_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Birth Certificate/Registration Number")
    )
    religion = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('Christianity', 'Christianity'),
            ('Islam', 'Islam'),
            ('Traditional', 'Traditional'),
            ('Other', 'Other'),
        ]
    )
    
    # Previous School Information
    previous_school = models.CharField(max_length=255, blank=True)
    previous_class = models.CharField(max_length=100, blank=True)
    last_report_card = models.FileField(
        upload_to='admissions/report_cards/',
        null=True,
        blank=True
    )
    
    # Medical Information
    medical_conditions = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    doctor_name = models.CharField(max_length=200, blank=True)
    doctor_phone = models.CharField(max_length=20, blank=True)
    
    # Student Photo
    student_photo = models.ImageField(
        upload_to='admissions/students/',
        null=True,
        blank=True
    )
    
    # Application Status & Tracking
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING
    )
    
    # Payment Information
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Payment reference number (e.g., Remita RRR, bank teller)")
    )
    payment_verified = models.BooleanField(default=False)
    payment_verified_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payments'
    )
    payment_verified_date = models.DateTimeField(null=True, blank=True)
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_("Application fee amount in Naira")
    )
    payment_channel = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('bank_deposit', 'Bank Deposit'),
            ('pos', 'POS'),
            ('online', 'Online Payment'),
            ('remita', 'Remita'),
            ('cash', 'Cash'),
        ]
    )
    payment_receipt = models.FileField(
        upload_to='admissions/payment_receipts/',
        null=True,
        blank=True,
        help_text=_("Upload payment receipt (optional)")
    )
    
    # PHASE 3: Review & Decision Tracking
    # Review tracking
    reviewed_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )
    review_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Decision tracking
    decision_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_applications'
    )
    decision_date = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    rejection_reason = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('capacity_full', 'Class Capacity Full'),
            ('academic_requirements', 'Academic Requirements Not Met'),
            ('age_requirement', 'Age Requirement Not Met'),
            ('documents_incomplete', 'Incomplete Documents'),
            ('interview_failed', 'Failed Interview/Assessment'),
            ('behavioral_issues', 'Previous Behavioral Issues'),
            ('financial', 'Financial Considerations'),
            ('other', 'Other Reasons'),
        ]
    )
    rejection_details = models.TextField(blank=True)
    
    # Approval details
    admission_letter_sent = models.BooleanField(default=False)
    admission_letter_sent_date = models.DateTimeField(null=True, blank=True)
    guardian_accepted = models.BooleanField(default=False)
    guardian_accepted_date = models.DateTimeField(null=True, blank=True)
    
    # Waitlist management
    waitlist_position = models.PositiveIntegerField(null=True, blank=True)
    waitlist_notes = models.TextField(blank=True)
    
    # If approved, link to created student
    created_student = models.OneToOneField(
        'students.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admission_application_link',
        verbose_name = _("Created Student")
    )
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_applications'
    )
    
    class Meta:
        ordering = ['-application_date', '-created_at']
        verbose_name = _('Admission Application')
        verbose_name_plural = _('Admission Applications')
        permissions = [
            ('verify_payment', 'Can verify payment references'),
            ('review_application', 'Can review admission applications'),
            ('make_admission_decision', 'Can approve/reject applications'),
            ('manage_waitlist', 'Can manage waitlisted applications'),
        ]
    
    def __str__(self):
        return f"{self.application_number} - {self.full_name}"
    
    def save(self, *args, **kwargs):
        # Generate application number if new
        if not self.application_number:
            year_month = timezone.now().strftime('%Y%m')
            last_app = AdmissionApplication.objects.filter(
                application_number__startswith=f'APP-{year_month}'
            ).order_by('-application_number').first()
            
            new_num = 1
            if last_app and last_app.application_number:
                try:
                    last_num = int(last_app.application_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    pass
            
            self.application_number = f"APP-{year_month}-{new_num:04d}"
        
        # Update verification date if payment verified
        if self.payment_verified and not self.payment_verified_date:
            self.payment_verified_date = timezone.now()
        
        # Update decision date if status changed to approved/rejected
        if self.status in [self.ApplicationStatus.APPROVED, self.ApplicationStatus.REJECTED] and not self.decision_date:
            self.decision_date = timezone.now()
        
        # Manage waitlist positions
        if self.status == self.ApplicationStatus.WAITLISTED and not self.waitlist_position:
            last_waitlist = AdmissionApplication.objects.filter(
                status=self.ApplicationStatus.WAITLISTED
            ).exclude(pk=self.pk).order_by('-waitlist_position').first()
            self.waitlist_position = (last_waitlist.waitlist_position + 1) if last_waitlist else 1
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate application rules"""
        errors = {}
        
        # Payment validation
        if self.payment_reference and not self.payment_verified:
            ref = self.payment_reference.strip()
            if not re.match(r'^[A-Z0-9]{6,20}$', ref, re.IGNORECASE):
                errors['payment_reference'] = _(
                    'Invalid payment reference format. '
                    'Use RRR, bank teller, or transaction ID (6-20 alphanumeric).'
                )
        
        # Status validation
        if self.status == self.ApplicationStatus.UNDER_REVIEW and not self.payment_verified:
            errors['status'] = _('Cannot review application without verified payment')
        
        if self.status == self.ApplicationStatus.APPROVED and not self.review_notes:
            errors['status'] = _('Review notes are required before approval')
        
        if self.status == self.ApplicationStatus.REJECTED and not self.rejection_reason:
            errors['rejection_reason'] = _('Rejection reason is required')
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def full_name(self):
        """Get student's full name"""
        if self.middle_name:
            return f"{self.surname} {self.first_name} {self.middle_name}"
        return f"{self.surname} {self.first_name}"
    
    @property
    def age(self):
        """Calculate age from date of birth"""
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    
    @property
    def can_be_reviewed(self):
        """Check if application can move to review"""
        return (self.status == self.ApplicationStatus.PENDING and 
                self.payment_verified)
    
    @property
    def can_be_decided(self):
        """Check if application can be approved/rejected"""
        return self.status == self.ApplicationStatus.UNDER_REVIEW
    
    @property
    def ready_for_student_creation(self):
        """Check if application is ready for student creation"""
        return (self.status == self.ApplicationStatus.APPROVED and 
                self.guardian_accepted and 
                not self.created_student)
    
    def get_status_badge_class(self):
        """Return Bootstrap badge class based on status"""
        status_classes = {
            'pending': 'secondary',
            'under_review': 'info',
            'approved': 'success',
            'rejected': 'danger',
            'waitlisted': 'warning',
            'accepted': 'primary',
        }
        return status_classes.get(self.status, 'secondary')

    
    def create_student(self, created_by=None):
        """Create student from this application"""
        from .services import StudentCreationService
        return StudentCreationService.create_student_from_application(
            self.pk, created_by
        )
    
    @property
    def can_create_student(self):
        """Check if student can be created from this application"""
        return (self.status == self.ApplicationStatus.APPROVED and 
                not hasattr(self, 'created_student') and
                self.admission_class and 
                self.admission_session)
    
    @property
    def student_creation_status(self):
        """Get student creation status"""
        if hasattr(self, 'created_student'):
            student = self.created_student
            return {
                'created': True,
                'student_number': student.student_number,
                'student_status': student.get_status_display(),
                'student_id': student.pk,
            }
        elif self.can_create_student:
            return {'created': False, 'ready': True}
        else:
            return {'created': False, 'ready': False, 'reason': 'Not approved or missing class/session'}


class AdmissionReviewLog(models.Model):
    """Audit log for admission reviews"""
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='review_logs'
    )
    staff = models.ForeignKey('staffs.Staff', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    notes = models.TextField(blank=True)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.application.application_number} - {self.action} by {self.staff}"