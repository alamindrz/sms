import csv

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import widgets
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from apps.finance.models import Invoice

from .models import Student, StudentBulkUpload, Guardian


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
        form.fields["others"].widget = widgets.Textarea(attrs={"rows": 2})
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
    """List all guardians"""
    model = Guardian
    template_name = 'students/guardian_list.html'
    permission_required = 'students.view_guardian'
    context_object_name = 'guardians'
    
    def get_queryset(self):
        return Guardian.objects.all().order_by('surname', 'firstname')

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