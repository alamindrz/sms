"""
Utilities for result safety and validation
"""
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.students.models import Student
from apps.corecode.models import AcademicSession, AcademicTerm, StudentClass

def validate_student_for_results(student_id, session_id=None, term_id=None):
    """
    Validate if a student can receive results
    
    Returns: (student, session, term)
    Raises: ValidationError if student cannot receive results
    """
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        raise ValidationError(_("Student not found"))
    
    # Check activation status
    is_active, missing = student.check_activation_status()
    if not is_active:
        raise ValidationError(
            _("Cannot enter results for inactive student. Missing: %(missing)s") % {
                'missing': ', '.join(missing)
            }
        )
    
    # Get session and term
    session = None
    term = None
    
    if session_id:
        try:
            session = AcademicSession.objects.get(pk=session_id)
        except AcademicSession.DoesNotExist:
            raise ValidationError(_("Academic session not found"))
    
    if term_id:
        try:
            term = AcademicTerm.objects.get(pk=term_id)
        except AcademicTerm.DoesNotExist:
            raise ValidationError(_("Academic term not found"))
    
    # Validate student is in correct session
    if session and student.current_session != session:
        raise ValidationError(
            _("Student is not enrolled in the selected academic session")
        )
    
    return student, session, term

def get_eligible_students_for_results(class_id=None, session_id=None, term_id=None):
    """
    Get students eligible for result entry
    """
    # Start with active students
    students = Student.get_active_students()
    
    # Filter by class if provided
    if class_id:
        students = students.filter(current_class_id=class_id)
    
    # Filter by session if provided
    if session_id:
        students = students.filter(current_session_id=session_id)
    
    # Order students
    students = students.select_related(
        'current_class', 'current_session', 'guardian'
    ).order_by('surname', 'firstname')
    
    return students

def check_bulk_result_eligibility(student_ids):
    """
    Check if multiple students are eligible for result entry
    
    Returns: (eligible_students, ineligible_students)
    """
    eligible = []
    ineligible = []
    
    for student_id in student_ids:
        try:
            student = Student.objects.get(pk=student_id)
            is_active, missing = student.check_activation_status()
            
            if is_active:
                eligible.append({
                    'id': student.id,
                    'name': student.full_name,
                    'number': student.student_number,
                    'class': str(student.current_class) if student.current_class else '',
                })
            else:
                ineligible.append({
                    'id': student.id,
                    'name': student.full_name,
                    'number': student.student_number,
                    'missing': missing,
                })
                
        except Student.DoesNotExist:
            ineligible.append({
                'id': student_id,
                'name': 'Unknown',
                'number': 'N/A',
                'missing': ['Student not found'],
            })
    
    return eligible, ineligible

def validate_promotion_eligibility(student_id, from_class_id, to_class_id, session_id):
    """
    Validate if a student can be promoted
    
    Returns: (student, from_class, to_class, session)
    Raises: ValidationError if student cannot be promoted
    """
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        raise ValidationError(_("Student not found"))
    
    # Check activation status
    is_active, missing = student.check_activation_status()
    if not is_active:
        raise ValidationError(
            _("Cannot promote inactive student. Missing: %(missing)s") % {
                'missing': ', '.join(missing)
            }
        )
    
    # Get classes
    try:
        from_class = StudentClass.objects.get(pk=from_class_id)
        to_class = StudentClass.objects.get(pk=to_class_id)
    except StudentClass.DoesNotExist:
        raise ValidationError(_("Class not found"))
    
    # Get session
    try:
        session = AcademicSession.objects.get(pk=session_id)
    except AcademicSession.DoesNotExist:
        raise ValidationError(_("Academic session not found"))
    
    # Validate student is in correct from_class
    if student.current_class != from_class:
        raise ValidationError(
            _("Student is not in the selected 'from' class")
        )
    
    # Validate student is in correct session
    if student.current_session != session:
        raise ValidationError(
            _("Student is not enrolled in the selected academic session")
        )
    
    return student, from_class, to_class, session

def get_promotion_candidates(class_id, session_id):
    """
    Get students eligible for promotion from a class
    """
    # Get active students in the class and session
    students = Student.get_active_students().filter(
        current_class_id=class_id,
        current_session_id=session_id
    ).select_related('current_class', 'current_session', 'guardian')
    
    # Check if students have required results
    # This would need to be implemented based on your result structure
    eligible_students = []
    
    for student in students:
        # Check if student has results for all terms in the session
        # For now, we'll assume all active students are eligible
        # You should implement proper result checking here
        eligible_students.append(student)
    
    return eligible_students