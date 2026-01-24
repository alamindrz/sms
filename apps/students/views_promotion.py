"""
Views for student promotion with safety checks
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, FormView, ListView
from django.urls import reverse_lazy
from django.db import transaction
from django.http import JsonResponse

from apps.students.models import Student
from apps.corecode.models import StudentClass, AcademicSession
from apps.result.utils import validate_promotion_eligibility, get_promotion_candidates
from apps.result.forms import PromotionEligibilityForm

class PromotionSafetyView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Check promotion eligibility before proceeding"""
    template_name = 'students/promotion_safety.html'
    form_class = PromotionEligibilityForm
    permission_required = 'students.change_student'
    success_url = reverse_lazy('students:promotion_confirm')
    
    def form_valid(self, form):
        # Store form data in session for next step
        self.request.session['promotion_data'] = {
            'from_class_id': form.cleaned_data['from_class'].id,
            'to_class_id': form.cleaned_data['to_class'].id,
            'session_id': form.cleaned_data['session'].id,
        }
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get promotion statistics
        context['total_students'] = Student.objects.count()
        context['active_students'] = Student.get_active_students().count()
        
        return context

@login_required
@permission_required('students.change_student', raise_exception=True)
def promotion_confirmation(request):
    """Confirm promotion with eligibility checks"""
    # Get promotion data from session
    promotion_data = request.session.get('promotion_data')
    
    if not promotion_data:
        messages.error(request, _("No promotion data found. Please start over."))
        return redirect('students:promotion_safety')
    
    try:
        from_class = StudentClass.objects.get(pk=promotion_data['from_class_id'])
        to_class = StudentClass.objects.get(pk=promotion_data['to_class_id'])
        session = AcademicSession.objects.get(pk=promotion_data['session_id'])
        
        # Get promotion candidates
        candidates = get_promotion_candidates(from_class.id, session.id)
        
        # Get ineligible students
        ineligible = Student.get_inactive_students().filter(
            current_class=from_class,
            current_session=session
        )
        
        if request.method == 'POST':
            # Process promotion
            student_ids = request.POST.getlist('student_ids[]')
            
            promoted_count = 0
            failed_count = 0
            errors = []
            
            with transaction.atomic():
                for student_id in student_ids:
                    try:
                        student = Student.objects.get(pk=student_id)
                        
                        # Validate eligibility
                        validate_promotion_eligibility(
                            student.id,
                            from_class.id,
                            to_class.id,
                            session.id
                        )
                        
                        # Promote student
                        student.current_class = to_class
                        student.save()
                        
                        # Create promotion log
                        PromotionLog.objects.create(
                            student=student,
                            from_class=from_class,
                            to_class=to_class,
                            session=session,
                            promoted_by=request.user.staff,
                            notes='Promoted via promotion system'
                        )
                        
                        promoted_count += 1
                        
                    except Exception as e:
                        failed_count += 1
                        errors.append(f"{student}: {str(e)}")
                
                # Show results
                if promoted_count > 0:
                    messages.success(
                        request,
                        _(f"Successfully promoted {promoted_count} students")
                    )
                
                if failed_count > 0:
                    messages.warning(
                        request,
                        _(f"Failed to promote {failed_count} students")
                    )
                    for error in errors[:5]:
                        messages.error(request, error)
                
                # Clear session data
                if 'promotion_data' in request.session:
                    del request.session['promotion_data']
                
                return redirect('students:student_list')
        
        return render(request, 'students/promotion_confirm.html', {
            'from_class': from_class,
            'to_class': to_class,
            'session': session,
            'candidates': candidates,
            'ineligible': ineligible,
            'total_candidates': len(candidates),
            'total_ineligible': len(ineligible),
        })
        
    except (StudentClass.DoesNotExist, AcademicSession.DoesNotExist):
        messages.error(request, _("Invalid promotion data"))
        return redirect('students:promotion_safety')

@login_required
@permission_required('students.change_student', raise_exception=True)
def check_promotion_eligibility_ajax(request):
    """AJAX endpoint to check promotion eligibility"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        from_class_id = request.POST.get('from_class_id')
        to_class_id = request.POST.get('to_class_id')
        session_id = request.POST.get('session_id')
        
        try:
            student, from_class, to_class, session = validate_promotion_eligibility(
                student_id, from_class_id, to_class_id, session_id
            )
            
            return JsonResponse({
                'success': True,
                'student': {
                    'id': student.id,
                    'name': student.full_name,
                    'number': student.student_number,
                },
                'message': _('Student is eligible for promotion')
            })
            
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

class PromotionLogView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View promotion logs"""
    model = PromotionLog
    template_name = 'students/promotion_logs.html'
    permission_required = 'students.view_student'
    paginate_by = 50
    
    def get_queryset(self):
        return PromotionLog.objects.all().select_related(
            'student', 'from_class', 'to_class', 'session', 'promoted_by'
        ).order_by('-promoted_at')

# Create PromotionLog model if it doesn't exist
from django.db import models

class PromotionLog(models.Model):
    """Log student promotions for audit trail"""
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    from_class = models.ForeignKey('corecode.StudentClass', on_delete=models.CASCADE, 
                                   related_name='promoted_from')
    to_class = models.ForeignKey('corecode.StudentClass', on_delete=models.CASCADE,
                                 related_name='promoted_to')
    session = models.ForeignKey('corecode.AcademicSession', on_delete=models.CASCADE)
    promoted_by = models.ForeignKey('staffs.Staff', on_delete=models.SET_NULL, null=True)
    promoted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-promoted_at']
    
    def __str__(self):
        return f"{self.student} promoted from {self.from_class} to {self.to_class}"