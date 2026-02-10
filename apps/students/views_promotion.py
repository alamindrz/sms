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
from django.db import transaction, models
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from .models import Student, PromotionLog
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
            # Get student IDs to promote
            student_ids = request.POST.getlist('student_ids[]')
            
            if not student_ids:
                messages.error(request, _("No students selected for promotion"))
                return redirect('students:promotion_safety')
            
            # Prepare promotion data for background processing
            promotion_batch = {
                'student_ids': [int(id) for id in student_ids],
                'from_class_id': from_class.id,
                'to_class_id': to_class.id,
                'session_id': session.id,
                'promoted_by_id': request.user.staff.id if hasattr(request.user, 'staff') else None,
            }
            
            try:
                # Import task function
                from tasks.student_tasks import process_promotion_batch
                
                # Queue the promotion batch
                task = process_promotion_batch.delay(promotion_batch)
                
                # Store task info in session for monitoring
                request.session['promotion_task'] = {
                    'task_id': task.id,
                    'student_count': len(student_ids),
                    'from_class': str(from_class),
                    'to_class': str(to_class),
                    'session': str(session),
                    'queued_at': timezone.now().isoformat(),
                }
                
                messages.info(
                    request,
                    _(f"Promotion of {len(student_ids)} students queued for background processing.")
                )
                messages.info(
                    request,
                    _(f"Task ID: {task.id}. You can check status in the task monitor.")
                )
                
                # Clear promotion data
                if 'promotion_data' in request.session:
                    del request.session['promotion_data']
                
                return redirect('students:promotion_task_status')
                
            except Exception as e:
                messages.error(request, _(f"Failed to queue promotion task: {str(e)}"))
                logger.error(f"Promotion task queuing failed: {str(e)}")
        
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
def promotion_task_status(request):
    """View promotion task status"""
    task_info = request.session.get('promotion_task', {})
    
    if not task_info:
        messages.warning(request, _("No active promotion task found"))
        return redirect('students:promotion_safety')
    
    # Check task status (simplified - in real app, use Celery result backend)
    from celery.result import AsyncResult
    from tasks.celery import app
    
    task_id = task_info.get('task_id')
    task = AsyncResult(task_id, app=app)
    
    context = {
        'task_info': task_info,
        'task_status': task.status if task else 'UNKNOWN',
        'task_result': task.result if task and task.ready() else None,
        'is_ready': task.ready() if task else False,
        'is_successful': task.successful() if task else False,
    }
    
    return render(request, 'students/promotion_task_status.html', context)

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