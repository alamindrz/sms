import csv

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import widgets
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.db.models import Count, Avg
from apps.finance.models import Invoice

from .models import Student, StudentBulkUpload, Guardian
from django.contrib.auth.decorators import login_required

class StudentListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = "students/student_list.html"


class StudentDetailView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = "students/student_detail.html"

    def get_context_data(self, **kwargs):
        context = super(StudentDetailView, self).get_context_data(**kwargs)
        context["payments"] = Invoice.objects.filter(student=self.object)
        return context


class StudentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Student
    fields = "__all__"
    success_message = "New student successfully added."

    def get_form(self):
        """add date picker in forms"""
        form = super(StudentCreateView, self).get_form()
        form.fields["date_of_birth"].widget = widgets.DateInput(attrs={"type": "date"})
        form.fields["address"].widget = widgets.Textarea(attrs={"rows": 2})

        return form


class StudentUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Student
    fields = "__all__"
    success_message = "Record successfully updated."

    def get_form(self):
        """add date picker in forms"""
        form = super(StudentUpdateView, self).get_form()
        form.fields["date_of_birth"].widget = widgets.DateInput(attrs={"type": "date"})
        form.fields["date_of_admission"].widget = widgets.DateInput(
            attrs={"type": "date"}
        )
        form.fields["address"].widget = widgets.Textarea(attrs={"rows": 2})
        form.fields["others"].widget = widgets.Textarea(attrs={"rows": 2})
        # form.fields['passport'].widget = widgets.FileInput()
        return form


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    model = Student
    success_url = reverse_lazy("student-list")


class StudentBulkUploadView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = StudentBulkUpload
    template_name = "students/students_upload.html"
    fields = ["csv_file"]
    success_url = "/student/list"
    success_message = "Successfully uploaded students"


class DownloadCSVViewdownloadcsv(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="student_template.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "registration_number",
                "surname",
                "firstname",
                "other_names",
                "gender",
                "parent_number",
                "address",
                "current_class",
            ]
        )

        return response





class GuardianListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List all guardians with optimized database queries and statistics.
    """
    model = Guardian
    template_name = 'students/guardian_list.html'
    permission_required = 'students.view_guardian'
    context_object_name = 'guardians'
    
    def get_queryset(self):
        """
        Optimized Queryset:
        1. Annotate each guardian with the count of their related students.
        2. Use the count in the table without hitting the DB for every row.
        """
        return Guardian.objects.all().annotate(
            student_count=Count('students')  # Adjust 'students' if your related_name is different
        ).order_by('surname', 'firstname')

    def get_context_data(self, **kwargs):
        """
        Calculate statistics for the header cards.
        """
        context = super().get_context_data(**kwargs)
        
        # 1. Get the total number of guardians
        total_guardians = self.get_queryset().count()
        
        # 2. Calculate average students per guardian
        # We perform this at the database level for performance
        avg_data = Guardian.objects.annotate(
            num_students=Count('students')
        ).aggregate(
            average=Avg('num_students')
        )
        
        context['total_guardians'] = total_guardians
        context['avg_students_per_guardian'] = avg_data['average'] or 0
        
        return context


class GuardianCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create a new guardian"""
    model = Guardian
    template_name = 'students/guardian_form.html'
    permission_required = 'students.add_guardian'
    fields = ['title', 'surname', 'firstname', 'other_name', 'email', 'phone', 
              'phone2', 'address', 'occupation', 'relationship', 'photo']
    success_url = reverse_lazy('students:guardian_list')
    
    def form_valid(self, form):
        messages.success(self.request, _("Guardian created successfully"))
        return super().form_valid(form)

class GuardianDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View guardian details"""
    model = Guardian
    template_name = 'students/guardian_detail.html'
    permission_required = 'students.view_guardian'
    context_object_name = 'guardian'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['students'] = self.object.students.all()
        return context

class GuardianUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update guardian information"""
    model = Guardian
    template_name = 'students/guardian_form.html'
    permission_required = 'students.change_guardian'
    fields = ['title', 'surname', 'firstname', 'other_name', 'email', 'phone', 
              'phone2', 'address', 'occupation', 'relationship', 'photo']
    
    def get_success_url(self):
        return reverse_lazy('students:guardian_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, _("Guardian updated successfully"))
        return super().form_valid(form)

class GuardianDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete a guardian"""
    model = Guardian
    template_name = 'students/guardian_confirm_delete.html'
    permission_required = 'students.delete_guardian'
    success_url = reverse_lazy('students:guardian_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Guardian deleted successfully"))
        return super().delete(request, *args, **kwargs)

# Add these function-based views if not already present

def student_activation_status_api(request, pk):
    """API endpoint to get student activation status"""
    student = get_object_or_404(Student, pk=pk)
    
    is_active, missing = student.check_activation_status()
    
    return JsonResponse({
        'student_id': student.pk,
        'student_number': student.student_number,
        'full_name': student.full_name,
        'is_active': is_active,
        'missing_requirements': missing,
        'activation_progress': student.get_activation_progress(),
        'has_guardian': bool(student.guardian),
        'has_class': bool(student.current_class),
        'has_session': bool(student.current_session),
        'status': student.status,
        'status_display': student.get_status_display(),
    })
    


@login_required
def task_monitor(request):
    """Simple task monitoring view"""
    from celery.result import AsyncResult
    from tasks.celery import app
    
    # Get recent uploads
    recent_uploads = StudentBulkUpload.objects.all().order_by('-date_uploaded')[:10]
    
    # Get recent guardian creations
    recent_guardians = Guardian.objects.filter(
        user_creation_status='processing'
    ).order_by('-id')[:10]
    
    # Check specific task if provided
    task_id = request.GET.get('task_id')
    task_info = None
    if task_id:
        try:
            task = AsyncResult(task_id, app=app)
            task_info = {
                'id': task_id,
                'status': task.status,
                'result': task.result if task.ready() else None,
                'ready': task.ready(),
                'successful': task.successful(),
                'failed': task.failed(),
            }
        except:
            pass
    
    context = {
        'recent_uploads': recent_uploads,
        'recent_guardians': recent_guardians,
        'task_info': task_info,
        'total_pending_uploads': StudentBulkUpload.objects.filter(task_status='pending').count(),
        'total_processing_uploads': StudentBulkUpload.objects.filter(task_status='processing').count(),
    }
    
    return render(request, 'students/task_monitor.html', context)


@login_required
def task_status_api(request, task_id):
    """API endpoint for task status"""
    from celery.result import AsyncResult
    from tasks.celery import app
    
    try:
        task = AsyncResult(task_id, app=app)
        
        response_data = {
            'task_id': task_id,
            'status': task.status,
            'ready': task.ready(),
            'successful': task.successful(),
            'failed': task.failed(),
        }
        
        if task.ready():
            response_data['result'] = task.result
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

