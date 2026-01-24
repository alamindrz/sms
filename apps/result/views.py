from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView, ListView
from django.urls import reverse_lazy
from django.db.models import Q, Avg, Sum, Count
from django.http import JsonResponse

from .models import Result, ResultBatch
from .forms import ResultForm, ResultBatchForm, BulkResultForm
from apps.students.models import Student
from apps.corecode.models import StudentClass, AcademicSession, AcademicTerm, Subject
from .utils import (
    validate_student_for_results,
    get_eligible_students_for_results,
    check_bulk_result_eligibility,
    validate_promotion_eligibility
)

class SafeResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create result with safety checks"""
    model = Result
    form_class = ResultForm
    template_name = 'result/safe_create_result.html'
    permission_required = 'result.add_result'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Additional validation before saving
        try:
            # Validate student eligibility
            validate_student_for_results(
                form.cleaned_data['student'].id,
                form.cleaned_data['session'].id,
                form.cleaned_data['term'].id
            )
            
            # Save the result
            response = super().form_valid(form)
            
            messages.success(self.request, _("Result created successfully"))
            return response
            
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get eligible students count for info
        context['eligible_count'] = Student.get_active_students().count()
        context['total_students'] = Student.objects.count()
        
        return context

class ResultBatchCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create result batch with safety checks"""
    model = ResultBatch
    form_class = ResultBatchForm
    template_name = 'result/result_batch_create.html'
    permission_required = 'result.add_result'
    success_url = reverse_lazy('result:batch_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user.staff
        
        # Check if there are eligible students
        eligible_students = form.instance.eligible_students
        
        if not eligible_students.exists():
            messages.error(
                self.request,
                _("No eligible students found for the selected class, session, and term")
            )
            return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            _("Result batch created. %(count)s students are eligible.") % {
                'count': eligible_students.count()
            }
        )
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available classes with active student counts
        classes = StudentClass.objects.all()
        class_data = []
        
        for cls in classes:
            active_count = Student.get_active_students().filter(
                current_class=cls
            ).count()
            
            if active_count > 0:
                class_data.append({
                    'class': cls,
                    'active_students': active_count,
                })
        
        context['class_data'] = class_data
        
        return context

@login_required
@permission_required('result.add_result', raise_exception=True)
def create_bulk_results(request, batch_id):
    """Create bulk results for a batch"""
    batch = get_object_or_404(ResultBatch, pk=batch_id)
    
    if request.method == 'POST':
        form = BulkResultForm(request.POST, batch=batch)
        if form.is_valid():
            # Process results
            results_created = 0
            results_updated = 0
            
            for student in batch.eligible_students:
                for subject in form.cleaned_data['subjects']:
                    # Create or update result
                    result, created = Result.objects.update_or_create(
                        student=student,
                        session=batch.session,
                        term=batch.term,
                        subject=subject,
                        defaults={
                            'test_score': form.cleaned_data.get('test_score', 0),
                            'exam_score': form.cleaned_data.get('exam_score', 0),
                        }
                    )
                    
                    if created:
                        results_created += 1
                    else:
                        results_updated += 1
            
            messages.success(
                request,
                _(f"Created {results_created} new results, updated {results_updated} results")
            )
            
            return redirect('result:batch_detail', pk=batch.id)
    else:
        form = BulkResultForm(batch=batch)
    
    return render(request, 'result/bulk_result_create.html', {
        'batch': batch,
        'form': form,
        'eligible_students': batch.eligible_students,
    })

@login_required
@permission_required('result.add_result', raise_exception=True)
def check_student_eligibility(request):
    """Check student eligibility for result entry (AJAX)"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        session_id = request.POST.get('session_id')
        term_id = request.POST.get('term_id')
        
        try:
            student, session, term = validate_student_for_results(
                student_id, session_id, term_id
            )
            
            return JsonResponse({
                'success': True,
                'student': {
                    'id': student.id,
                    'name': student.full_name,
                    'number': student.student_number,
                    'class': str(student.current_class) if student.current_class else '',
                },
                'message': _('Student is eligible for result entry')
            })
            
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@permission_required('result.add_result', raise_exception=True)
def check_bulk_eligibility(request):
    """Check bulk eligibility for result entry"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids[]')
        session_id = request.POST.get('session_id')
        term_id = request.POST.get('term_id')
        
        eligible, ineligible = check_bulk_result_eligibility(student_ids)
        
        return JsonResponse({
            'eligible_count': len(eligible),
            'ineligible_count': len(ineligible),
            'eligible': eligible,
            'ineligible': ineligible,
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

class ResultValidationView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """View to validate results before entry"""
    template_name = 'result/result_validation.html'
    permission_required = 'result.add_result'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        class_id = self.request.GET.get('class_id')
        session_id = self.request.GET.get('session_id')
        term_id = self.request.GET.get('term_id')
        
        # Get eligible students
        students = get_eligible_students_for_results(class_id, session_id, term_id)
        
        # Get ineligible students (for comparison)
        ineligible = Student.get_inactive_students()
        if class_id:
            ineligible = ineligible.filter(current_class_id=class_id)
        
        context['students'] = students
        context['ineligible_students'] = ineligible[:10]  # First 10 for preview
        
        # Get filter options
        context['classes'] = StudentClass.objects.all()
        context['sessions'] = AcademicSession.objects.all()
        context['terms'] = AcademicTerm.objects.all()
        
        return context

@login_required
@permission_required('result.add_result', raise_exception=True)
def export_eligible_students(request):
    """Export list of eligible students for result entry"""
    class_id = request.GET.get('class_id')
    session_id = request.GET.get('session_id')
    term_id = request.GET.get('term_id')
    
    students = get_eligible_students_for_results(class_id, session_id, term_id)
    
    # Create CSV response
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="eligible_students.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Full Name', 'Class', 'Guardian', 'Phone', 'Email'])
    
    for student in students:
        writer.writerow([
            student.student_number,
            student.full_name,
            str(student.current_class) if student.current_class else '',
            student.guardian.full_name if student.guardian else '',
            student.guardian.phone if student.guardian and student.guardian.phone else '',
            student.guardian.email if student.guardian and student.guardian.email else '',
        ])
    
    return response