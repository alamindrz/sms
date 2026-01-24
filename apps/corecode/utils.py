"""
Utility functions for class and session enforcement
"""
from django.utils.translation import gettext_lazy as _
from apps.students.models import Student

def check_student_activation(student):
    """
    Check if a student is active and ready for academic operations
    
    Returns: (is_active, missing_requirements)
    """
    missing = []
    
    if not student.guardian:
        missing.append(_("Guardian"))
    
    if not student.current_class:
        missing.append(_("Class"))
    
    if not student.current_session:
        missing.append(_("Academic Session"))
    
    is_active = len(missing) == 0 and student.status == Student.Status.ACTIVE
    
    return is_active, missing

def filter_active_students(queryset):
    """Filter queryset to only include active students"""
    return queryset.filter(
        status=Student.Status.ACTIVE,
        guardian__isnull=False,
        current_class__isnull=False,
        current_session__isnull=False
    )

def filter_inactive_students(queryset):
    """Filter queryset to only include inactive students"""
    return queryset.filter(
        status=Student.Status.INACTIVE
    ) | queryset.filter(
        Q(guardian__isnull=True) |
        Q(current_class__isnull=True) |
        Q(current_session__isnull=True)
    )

def get_student_activation_status(student):
    """Get detailed activation status for a student"""
    is_active, missing = check_student_activation(student)
    
    return {
        'is_active': is_active,
        'missing': missing,
        'can_be_activated': len(missing) == 0,
        'status_display': student.get_status_display(),
        'has_guardian': bool(student.guardian),
        'has_class': bool(student.current_class),
        'has_session': bool(student.current_session),
    }

def validate_student_for_academic_operations(student):
    """
    Validate if student can participate in academic operations
    
    Raises: ValidationError if student cannot participate
    """
    from django.core.exceptions import ValidationError
    
    is_active, missing = check_student_activation(student)
    
    if not is_active:
        raise ValidationError(
            _("Student is not active. Missing: %(missing)s") % {
                'missing': ', '.join(missing)
            }
        )