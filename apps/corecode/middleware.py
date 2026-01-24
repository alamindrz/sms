from .models import AcademicSession, AcademicTerm
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from apps.students.models import Student

class SiteWideConfigs:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_session = AcademicSession.objects.get(current=True)
        current_term = AcademicTerm.objects.get(current=True)

        request.current_session = current_session
        request.current_term = current_term

        response = self.get_response(request)

        return response
        
        


class StudentActivationMiddleware(MiddlewareMixin):
    """
    Middleware to check student activation status and provide warnings
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip for non-staff users and certain views
        if not request.user.is_authenticated or not request.user.is_staff:
            return None
        
        # Check if we're dealing with student operations
        student_id = view_kwargs.get('pk') or view_kwargs.get('student_id')
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                
                # Check activation status
                is_active, missing = student.check_activation_status()
                
                if not is_active and missing:
                    # Add warning message for staff
                    messages.warning(
                        request,
                        _('Student %(name)s is inactive. Missing: %(missing)s') % {
                            'name': student.full_name,
                            'missing': ', '.join(missing)
                        }
                    )
                    
            except Student.DoesNotExist:
                pass
        
        return None

class ClassSessionEnforcementMiddleware(MiddlewareMixin):
    """
    Middleware to prevent operations on inactive students
    """
    
    BLOCKED_PATTERNS = [
        '/result/',
        '/finance/invoice/create/',
        '/attendance/',
    ]
    
    ALLOWED_PATTERNS = [
        '/students/activate/',
        '/admissions/student_activate/',
        '/admissions/inactive_students/',
    ]
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip for non-staff users
        if not request.user.is_authenticated or not request.user.is_staff:
            return None
        
        # Check if this is a blocked pattern
        path = request.path
        
        # Skip allowed patterns
        for allowed in self.ALLOWED_PATTERNS:
            if allowed in path:
                return None
        
        # Check if this is a blocked pattern
        should_check = False
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in path:
                should_check = True
                break
        
        if not should_check:
            return None
        
        # Check for student ID in request
        student_id = None
        
        # Check URL kwargs
        student_id = view_kwargs.get('pk') or view_kwargs.get('student_id')
        
        # Check POST data
        if not student_id and request.method == 'POST':
            student_id = request.POST.get('student') or request.POST.get('student_id')
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                
                # Check if student is active
                is_active, missing = student.check_activation_status()
                
                if not is_active:
                    messages.error(
                        request,
                        _('Cannot perform this operation. Student %(name)s is inactive.') % {
                            'name': student.full_name
                        }
                    )
                    
                    # Redirect back or to student activation page
                    from django.shortcuts import redirect
                    return redirect('admissions:student_activate', pk=student_id)
                    
            except Student.DoesNotExist:
                pass
        
        return None