from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.corecode.models import StudentClass

from django.core.exceptions import ValidationError
import uuid



class Student(models.Model):
    """Student model with hybrid workflow support"""
    
    class CreationMethod(models.TextChoices):
        MANUAL = 'manual', _('Manual Entry')
        ADMISSION = 'admission', _('Admission System')
        IMPORT = 'import', _('Bulk Import')
        MIGRATION = 'migration', _('Data Migration')
    
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        GRADUATED = 'graduated', _('Graduated')
        WITHDRAWN = 'withdrawn', _('Withdrawn')
        SUSPENDED = 'suspended', _('Suspended')
    
    # PHASE 4: Student Creation Tracking
    created_via = models.CharField(
        max_length=20,
        choices=CreationMethod.choices,
        default=CreationMethod.MANUAL,
        verbose_name=_("Creation Method")
    )
    
    # Student Information
    student_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Student ID"),
        help_text=_("Auto-generated student number")
    )
    surname = models.CharField(max_length=200, verbose_name=_("Surname"))
    firstname = models.CharField(max_length=200, verbose_name=_("First Name"))
    other_name = models.CharField(max_length=200, blank=True, verbose_name=_("Other Name"))
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female')],
        verbose_name=_("Gender")
    )
    date_of_birth = models.DateField(verbose_name=_("Date of Birth"))
    
    # Contact Information
    mobile_number = models.CharField(max_length=20, blank=True, verbose_name=_("Mobile Number"))
    email = models.EmailField(blank=True, verbose_name=_("Email"))
    address = models.TextField(blank=True, verbose_name=_("Address"))
    
    # Academic Information
    current_class = models.ForeignKey(
        'corecode.StudentClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Current Class")
    )
    current_session = models.ForeignKey(
        'corecode.AcademicSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Current Session")
    )
    
    # Medical Information
    medical_conditions = models.TextField(blank=True, verbose_name=_("Medical Conditions"))
    allergies = models.TextField(blank=True, verbose_name=_("Allergies"))
    
    # Photo and Documents
    passport = models.ImageField(
        upload_to='students/passports/',
        blank=True,
        verbose_name=_("Passport Photo")
    )
    
    # Guardian Information
    guardian = models.ForeignKey(
        'students.Guardian',  # We'll create this model next
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name=_("Guardian/Parent")
    )
    
    # Status and Tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INACTIVE,
        verbose_name=_("Status")
    )
    
    # Admission Application Link
    admission_record = models.OneToOneField(
        'admissions.AdmissionApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_student_link',
        verbose_name=_("Admission Record")
    )
    
    # Dates
    admission_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Admission Date")
    )
    graduation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Graduation Date")
    )
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By")
    )
    
    class Meta:
        ordering = ['student_number', 'surname', 'firstname']
        verbose_name = _('Student')
        verbose_name_plural = _('Students')
        permissions = [
            ('activate_student', 'Can activate students'),
            ('deactivate_student', 'Can deactivate students'),
        ]
    
    def __str__(self):
        return f"{self.student_number} - {self.full_name}"
    
    def save(self, *args, **kwargs):
        # Generate student number if new
        if not self.student_number:
            self.student_number = self.generate_student_number()
        
        # Set admission date for admission-created students
        if self.admission_application and not self.admission_date:
            self.admission_date = self.admission_application.application_date
        
        super().save(*args, **kwargs)
    
    def generate_student_number(self):
        """Generate unique student number based on creation method"""
        if self.created_via == self.CreationMethod.ADMISSION and self.admission_application:
            # Use admission application number as base
            app_num = self.admission_application.application_number.replace('APP-', 'STU-')
            return app_num
        
        # Generate based on year and sequence
        year = timezone.now().year
        prefix = {
            self.CreationMethod.MANUAL: 'M',
            self.CreationMethod.ADMISSION: 'A',
            self.CreationMethod.IMPORT: 'I',
            self.CreationMethod.MIGRATION: 'G',
        }.get(self.created_via, 'S')
        
        last_student = Student.objects.filter(
            student_number__startswith=f'{prefix}{year}'
        ).order_by('-student_number').first()
        
        if last_student and last_student.student_number:
            try:
                last_num = int(last_student.student_number[-4:])
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{year}{new_num:04d}"
    
    @property
    def full_name(self):
        """Get full name"""
        if self.other_name:
            return f"{self.surname} {self.firstname} {self.other_name}"
        return f"{self.surname} {self.firstname}"
    
    @property
    def age(self):
        """Calculate age from date of birth"""
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    
    @property
    def is_activatable(self):
        """Check if student can be activated"""
        return (self.guardian is not None and 
                self.current_class is not None and 
                self.current_session is not None)
    
    def activate(self):
        """Activate the student"""
        if self.is_activatable:
            self.status = self.Status.ACTIVE
            self.save()
            return True
        return False
    
    def deactivate(self):
        """Deactivate the student"""
        self.status = self.Status.INACTIVE
        self.save()
    
    def clean(self):
        """Validate student data"""
        errors = {}
        
        # Check activation requirements
        if self.status == self.Status.ACTIVE and not self.is_activatable:
            errors['status'] = _(
                "Student cannot be active without guardian, class, and session"
            )
        
        # Validate admission application link
        if self.admission_application:
            if self.admission_application.status != 'approved':
                errors['admission_application'] = _(
                    "Can only link to approved admission applications"
                )
            if hasattr(self.admission_application, 'created_student'):
                if self.admission_application.created_student and self.admission_application.created_student.pk != self.pk:
                    errors['admission_application'] = _(
                        "This admission application is already linked to another student"
                    )
        
        if errors:
            raise ValidationError(errors)
    
    def get_activation_requirements(self):
        """Get missing activation requirements"""
        requirements = []
        if not self.guardian:
            requirements.append(_("Guardian/Parent"))
        if not self.current_class:
            requirements.append(_("Class"))
        if not self.current_session:
            requirements.append(_("Academic Session"))
        return requirements
        
    

    def check_activation_status(self):
        """Check if student can be activated"""
        from apps.corecode.utils import check_student_activation
        return check_student_activation(self)
    
    def validate_for_academic_operations(self):
        """Validate student for academic operations"""
        from apps.corecode.utils import validate_student_for_academic_operations
        return validate_student_for_academic_operations(self)
    
    @classmethod
    def get_active_students(cls):
        """Get all active students"""
        return cls.objects.filter(
            status=cls.Status.ACTIVE,
            guardian__isnull=False,
            current_class__isnull=False,
            current_session__isnull=False
        )
    
    @classmethod
    def get_inactive_students(cls):
        """Get all inactive students"""
        return cls.objects.filter(
            status=cls.Status.INACTIVE
        ) | cls.objects.filter(
            Q(guardian__isnull=True) |
            Q(current_class__isnull=True) |
            Q(current_session__isnull=True)
        )
    
    def get_activation_progress(self):
        """Get activation progress as percentage"""
        requirements = ['guardian', 'current_class', 'current_session']
        met = 0
        
        if self.guardian:
            met += 1
        if self.current_class:
            met += 1
        if self.current_session:
            met += 1
        
        return int((met / len(requirements)) * 100)

# Create Guardian Model
class Guardian(models.Model):
    """Guardian/Parent model"""
    
    # Basic Information
    title = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('Mr', 'Mr'),
            ('Mrs', 'Mrs'),
            ('Miss', 'Miss'),
            ('Dr', 'Dr'),
            ('Prof', 'Prof'),
            ('Chief', 'Chief'),
            ('Alhaji', 'Alhaji'),
            ('Alhaja', 'Alhaja'),
        ]
    )
    surname = models.CharField(max_length=200)
    firstname = models.CharField(max_length=200)
    other_name = models.CharField(max_length=200, blank=True)
    
    # Contact Information
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    phone2 = models.CharField(max_length=20, blank=True)
    address = models.TextField()
    occupation = models.CharField(max_length=200, blank=True)
    
    # Relationship to Student
    relationship = models.CharField(
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
    
    # User Account (optional)
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guardian_profile'
    )
    
    # Photo
    photo = models.ImageField(
        upload_to='guardians/photos/',
        null=True,
        blank=True
    )
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['surname', 'firstname']
        verbose_name = _('Guardian')
        verbose_name_plural = _('Guardians')
    
    def __str__(self):
        return f"{self.full_name} ({self.phone})"
    
    @property
    def full_name(self):
        """Get full name"""
        name_parts = []
        if self.title:
            name_parts.append(self.title)
        name_parts.append(self.surname)
        name_parts.append(self.firstname)
        if self.other_name:
            name_parts.append(self.other_name)
        return " ".join(name_parts)
    
    @property
    def active_students(self):
        """Get active students under this guardian"""
        return self.students.filter(status=Student.Status.ACTIVE)
    
    @property
    def all_students(self):
        """Get all students under this guardian"""
        return self.students.all()
    
    def create_user_account(self):
        """Create a user account for the guardian"""
        from django.contrib.auth.models import User
        
        if not self.user:
            username = f"{self.email.split('@')[0]}_{self.id}"
            user = User.objects.create_user(
                username=username,
                email=self.email,
                password=User.objects.make_random_password()
            )
            user.first_name = self.firstname
            user.last_name = self.surname
            user.save()
            self.user = user
            self.save()
            
            # Send welcome email with password reset link
            self.send_welcome_email()
    
    def send_welcome_email(self):
        """Send welcome email to guardian"""
        from django.core.mail import send_mail
        from django.conf import settings
        from django.urls import reverse
        
        subject = f"Welcome to {settings.SCHOOL_NAME} Parent Portal"
        reset_url = reverse('password_reset')
        
        message = f"""
        Dear {self.full_name},
        
        Welcome to the {settings.SCHOOL_NAME} Parent Portal!
        
        Your account has been created with the following details:
        - Username: {self.user.username}
        - Email: {self.email}
        
        To access the portal, please:
        1. Go to: {settings.SITE_URL}
        2. Click "Forgot Password"
        3. Enter your email: {self.email}
        4. Follow the instructions to set your password
        
        You will be able to:
        - View your ward's academic progress
        - Check fee payments
        - Receive school announcements
        - Update your contact information
        
        Best regards,
        {settings.SCHOOL_NAME}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.email],
            fail_silently=True,
        )


class StudentBulkUpload(models.Model):
    date_uploaded = models.DateTimeField(auto_now=True)
    csv_file = models.FileField(upload_to="students/bulkupload/")
