"""
Services for student creation from admission applications
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.students.models import Student, Guardian
from apps.corecode.models import StudentClass, AcademicSession
from .models import AdmissionApplication
import logging

logger = logging.getLogger(__name__)

class StudentCreationError(Exception):
    """Custom exception for student creation errors"""
    pass

class StudentCreationService:
    """Service for creating students from admission applications"""
    
    @classmethod
    def create_student_from_application(cls, application_id, created_by=None):
        """
        Create a student from an approved admission application
        
        Args:
            application_id: ID of the admission application
            created_by: Staff member creating the student
            
        Returns:
            Student: The created student
        """
        try:
            with transaction.atomic():
                # Get the application
                application = AdmissionApplication.objects.select_for_update().get(
                    pk=application_id,
                    status=AdmissionApplication.ApplicationStatus.APPROVED
                )
                
                # Check if student already exists
                if hasattr(application, 'created_student'):
                    raise StudentCreationError(
                        _("Student already created from this application")
                    )
                
                # Create guardian
                guardian = cls.create_guardian_from_application(application)
                
                # Get class and session
                student_class = application.admission_class
                session = application.admission_session
                
                if not student_class or not session:
                    raise StudentCreationError(
                        _("Application must have class and session assigned")
                    )
                
                # Create student
                student = Student(
                    # Personal Information
                    surname=application.surname,
                    firstname=application.first_name,
                    other_name=application.middle_name,
                    gender=application.gender,
                    date_of_birth=application.date_of_birth,
                    
                    # Contact Information
                    email=application.guardian_email,  # Use guardian email initially
                    mobile_number=application.guardian_phone,
                    address=application.guardian_address,
                    
                    # Academic Information
                    current_class=student_class,
                    current_session=session,
                    
                    # Medical Information
                    medical_conditions=application.medical_conditions,
                    allergies=application.allergies,
                    
                    # Photo
                    passport=application.student_photo,
                    
                    # Guardian Link
                    guardian=guardian,
                    
                    # Creation Tracking
                    created_via=Student.CreationMethod.ADMISSION,
                    admission_application=application,
                    admission_date=application.application_date,
                    
                    # Created By
                    created_by=created_by,
                    
                    # Initially inactive (needs activation)
                    status=Student.Status.INACTIVE,
                )
                
                student.save()
                
                # Update application with student link
                application.created_student = student
                application.save()
                
                # Create guardian user account
                try:
                    guardian.create_user_account()
                except Exception as e:
                    logger.warning(f"Failed to create guardian account: {e}")
                    # Don't fail student creation if account creation fails
                
                # Log the creation
                from .models import AdmissionReviewLog
                AdmissionReviewLog.objects.create(
                    application=application,
                    staff=created_by,
                    action='STUDENT_CREATED',
                    notes=f'Student {student.student_number} created from application',
                    from_status=application.status,
                    to_status=application.status
                )
                
                logger.info(f"Student created: {student.student_number} from {application.application_number}")
                return student
                
        except AdmissionApplication.DoesNotExist:
            raise StudentCreationError(_("Application not found or not approved"))
        except Exception as e:
            logger.error(f"Student creation failed: {e}")
            raise StudentCreationError(str(e))
    
    @classmethod
    def create_guardian_from_application(cls, application):
        """
        Create or update guardian from application data
        
        Args:
            application: AdmissionApplication instance
            
        Returns:
            Guardian: The created/updated guardian
        """
        # Check if guardian with this email already exists
        try:
            guardian = Guardian.objects.get(email=application.guardian_email)
            
            # Update existing guardian with application data if needed
            if not guardian.phone:
                guardian.phone = application.guardian_phone
            if not guardian.address:
                guardian.address = application.guardian_address
            if not guardian.photo and application.guardian_photo:
                guardian.photo = application.guardian_photo
            
            guardian.save()
            return guardian
            
        except Guardian.DoesNotExist:
            # Create new guardian
            # Parse guardian name
            guardian_name_parts = application.guardian_name.split()
            if len(guardian_name_parts) >= 2:
                surname = guardian_name_parts[0]
                firstname = guardian_name_parts[1]
                other_name = ' '.join(guardian_name_parts[2:]) if len(guardian_name_parts) > 2 else ''
            else:
                surname = application.guardian_name
                firstname = ""
                other_name = ""
            
            guardian = Guardian(
                surname=surname,
                firstname=firstname,
                other_name=other_name,
                email=application.guardian_email,
                phone=application.guardian_phone,
                address=application.guardian_address,
                relationship=application.guardian_relationship,
                photo=application.guardian_photo,
            )
            guardian.save()
            return guardian
    
    @classmethod
    def bulk_create_students(cls, application_ids, created_by):
        """
        Bulk create students from multiple applications
        
        Args:
            application_ids: List of application IDs
            created_by: Staff member
            
        Returns:
            dict: Results with success/failure counts
        """
        results = {
            'total': len(application_ids),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for app_id in application_ids:
            try:
                student = cls.create_student_from_application(app_id, created_by)
                results['success'] += 1
            except StudentCreationError as e:
                results['failed'] += 1
                results['errors'].append({
                    'application_id': app_id,
                    'error': str(e)
                })
        
        return results
    
    @classmethod
    def activate_student(cls, student_id, activated_by=None):
        """
        Activate a student (make them active)
        
        Args:
            student_id: Student ID
            activated_by: Staff member activating
            
        Returns:
            bool: Success status
        """
        try:
            student = Student.objects.get(pk=student_id)
            
            if student.status == Student.Status.ACTIVE:
                return True
            
            if not student.is_activatable:
                missing = student.get_activation_requirements()
                raise StudentCreationError(
                    _("Cannot activate student. Missing: {}").format(", ".join(missing))
                )
            
            student.activate()
            
            # Log the activation
            from .models import AdmissionReviewLog
            if student.admission_application:
                AdmissionReviewLog.objects.create(
                    application=student.admission_application,
                    staff=activated_by,
                    action='STUDENT_ACTIVATED',
                    notes=f'Student {student.student_number} activated',
                    from_status=student.status,
                    to_status=Student.Status.ACTIVE
                )
            
            # Send activation notification
            cls.send_activation_notification(student)
            
            return True
            
        except Student.DoesNotExist:
            raise StudentCreationError(_("Student not found"))
        except Exception as e:
            logger.error(f"Student activation failed: {e}")
            raise StudentCreationError(str(e))
    
    @classmethod
    def send_activation_notification(cls, student):
        """Send notification about student activation"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        if not student.guardian or not student.guardian.email:
            return
        
        subject = f"Student Activated - {student.student_number}"
        
        message = f"""
        Dear {student.guardian.full_name},
        
        We are pleased to inform you that {student.full_name} has been 
        activated in our school system with the following details:
        
        Student Number: {student.student_number}
        Class: {student.current_class}
        Session: {student.current_session}
        Status: Active
        
        Your ward can now:
        - Appear in class lists
        - Receive academic results
        - Participate in school activities
        - Generate school fees
        
        Please ensure all required documents are submitted to the school office.
        
        Welcome to {settings.SCHOOL_NAME}!
        
        Best regards,
        {settings.SCHOOL_NAME}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.guardian.email],
            fail_silently=True,
        )

class StudentActivationService:
    """Service for student activation workflows"""
    
    @classmethod
    def get_pending_activations(cls):
        """Get students pending activation"""
        return Student.objects.filter(
            status=Student.Status.INACTIVE,
            admission_application__isnull=False
        ).select_related(
            'guardian', 'current_class', 'current_session', 'admission_application'
        )
    
    @classmethod
    def bulk_activate_students(cls, student_ids, activated_by):
        """
        Bulk activate multiple students
        
        Args:
            student_ids: List of student IDs
            activated_by: Staff member
            
        Returns:
            dict: Results
        """
        results = {
            'total': len(student_ids),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for student_id in student_ids:
            try:
                StudentCreationService.activate_student(student_id, activated_by)
                results['success'] += 1
            except StudentCreationError as e:
                results['failed'] += 1
                results['errors'].append({
                    'student_id': student_id,
                    'error': str(e)
                })
        
        return results

class ManualStudentCreationService:
    """Service for manual student creation"""
    
    @classmethod
    def create_manual_student(cls, data, created_by=None):
        """
        Create a student manually
        
        Args:
            data: Dictionary with student data
            created_by: Staff member
            
        Returns:
            Student: Created student
        """
        try:
            with transaction.atomic():
                # Create guardian if provided
                guardian = None
                if data.get('guardian_email'):
                    guardian = cls.get_or_create_guardian(data)
                
                # Create student
                student = Student(
                    surname=data.get('surname'),
                    firstname=data.get('firstname'),
                    other_name=data.get('other_name', ''),
                    gender=data.get('gender'),
                    date_of_birth=data.get('date_of_birth'),
                    
                    # Contact
                    email=data.get('email', ''),
                    mobile_number=data.get('mobile_number', ''),
                    address=data.get('address', ''),
                    
                    # Academic
                    current_class=data.get('current_class'),
                    current_session=data.get('current_session'),
                    
                    # Medical
                    medical_conditions=data.get('medical_conditions', ''),
                    allergies=data.get('allergies', ''),
                    
                    # Photo
                    passport=data.get('passport'),
                    
                    # Guardian
                    guardian=guardian,
                    
                    # Creation method
                    created_via=Student.CreationMethod.MANUAL,
                    created_by=created_by,
                    
                    # Status (initially inactive)
                    status=Student.Status.INACTIVE,
                )
                
                student.save()
                
                logger.info(f"Manual student created: {student.student_number}")
                return student
                
        except Exception as e:
            logger.error(f"Manual student creation failed: {e}")
            raise StudentCreationError(str(e))
    
    @classmethod
    def get_or_create_guardian(cls, data):
        """Get existing guardian or create new one"""
        email = data.get('guardian_email')
        if not email:
            return None
        
        try:
            return Guardian.objects.get(email=email)
        except Guardian.DoesNotExist:
            guardian = Guardian(
                surname=data.get('guardian_surname', ''),
                firstname=data.get('guardian_firstname', ''),
                other_name=data.get('guardian_other_name', ''),
                email=email,
                phone=data.get('guardian_phone', ''),
                address=data.get('guardian_address', ''),
                relationship=data.get('guardian_relationship', 'Parent'),
            )
            guardian.save()
            return guardian