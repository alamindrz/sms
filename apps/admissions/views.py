from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, UpdateView, ListView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.db.models import Q

from .models import AdmissionApplication
from django.views.generic import FormView
from django.contrib import messages
from django.db import transaction
from apps.students.models import Student, Guardian
from .services import (
    StudentCreationService, 
    StudentActivationService,
    StudentCreationError
)
from .forms_student import (
    CreateStudentForm,
    BulkCreateStudentsForm,
    StudentActivationForm,
    BulkActivationForm,
    EnhancedManualStudentForm,
    QuickStudentForm,
    StudentActivationForm
)

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView, ListView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Case, When, IntegerField
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import AdmissionApplication, AdmissionReviewLog
from .forms import (
    AdmissionApplicationForm, 
    AdmissionReviewForm, 
    PaymentVerificationForm,
    BulkPaymentVerificationForm,
    AdmissionDecisionForm,
    BulkDecisionForm,
    WaitlistManagementForm,
    SendAdmissionLetterForm
)







class AdmissionApplicationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all admission applications"""
    model = AdmissionApplication
    template_name = 'admissions/application_list.html'
    context_object_name = 'applications'
    permission_required = 'admissions.view_admissionapplication'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.GET.get('status')
        payment_status = self.request.GET.get('payment_status')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if payment_status == 'verified':
            queryset = queryset.filter(payment_verified=True)
        elif payment_status == 'unverified':
            queryset = queryset.filter(payment_verified=False)
        elif payment_status == 'unpaid':
            queryset = queryset.filter(payment_reference='')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = AdmissionApplication.ApplicationStatus.choices
        
        # Stats for dashboard
        context['total_applications'] = AdmissionApplication.objects.count()
        context['pending_payment'] = AdmissionApplication.objects.filter(
            Q(payment_reference='') | Q(payment_verified=False)
        ).count()
        context['pending_review'] = AdmissionApplication.objects.filter(
            status='pending',
            payment_verified=True
        ).count()
        
        return context

class AdmissionApplicationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View admission application details"""
    model = AdmissionApplication
    template_name = 'admissions/application_detail.html'
    context_object_name = 'application'
    permission_required = 'admissions.view_admissionapplication'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment_form'] = PaymentVerificationForm(instance=self.object)
        return context

class CreateAdmissionApplicationView(CreateView):
    """Public view for submitting admission applications"""
    model = AdmissionApplication
    form_class = AdmissionApplicationForm
    template_name = 'admissions/application_create.html'
    success_url = reverse_lazy('admissions:application_submitted')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if admissions are open (from site config)
        from apps.corecode.models import SiteConfig
        try:
            config = SiteConfig.objects.first()
            context['admissions_open'] = config.admissions_open if config else True
            context['application_fee'] = config.application_fee if config else 5000.00
        except:
            context['admissions_open'] = True
            context['application_fee'] = 5000.00
        
        return context
    
    def form_valid(self, form):
        # Set admission session/class based on current session
        from apps.corecode.models import AcademicSession, SiteConfig
        
        try:
            current_session = AcademicSession.objects.get(current=True)
            form.instance.admission_session = current_session
        except AcademicSession.DoesNotExist:
            pass
        
        # Set application fee from site config
        try:
            config = SiteConfig.objects.first()
            if config:
                form.instance.payment_amount = config.application_fee
        except:
            form.instance.payment_amount = 5000.00
        
        messages.success(
            self.request,
            _("Application submitted successfully! Your application number is {}").format(
                form.instance.application_number
            )
        )
        return super().form_valid(form)

class ReviewAdmissionApplicationView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Review an admission application"""
    model = AdmissionApplication
    form_class = AdmissionReviewForm
    template_name = 'admissions/application_review.html'
    permission_required = 'admissions.change_admissionapplication'
    
    def form_valid(self, form):
        if form.instance.status == AdmissionApplication.ApplicationStatus.UNDER_REVIEW:
            form.instance.reviewed_by = self.request.user.staff
            form.instance.review_date = timezone.now()
        
        messages.success(self.request, _("Application review updated successfully"))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('admissions:application_detail', kwargs={'pk': self.object.pk})

class VerifyPaymentView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Verify payment for an admission application"""
    model = AdmissionApplication
    form_class = PaymentVerificationForm
    template_name = 'admissions/payment_verify.html'
    permission_required = 'admissions.verify_payment'
    
    def form_valid(self, form):
        if form.instance.payment_verified and not form.instance.payment_verified_by:
            form.instance.payment_verified_by = self.request.user.staff
            form.instance.payment_verified_date = timezone.now()
        
        messages.success(self.request, _("Payment verification updated"))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('admissions:application_detail', kwargs={'pk': self.object.pk})

@login_required
@permission_required('admissions.verify_payment', raise_exception=True)
def bulk_verify_payments(request):
    """Bulk verify multiple payments"""
    if request.method == 'POST':
        form = BulkPaymentVerificationForm(request.POST)
        if form.is_valid():
            app_numbers = form.cleaned_data['app_numbers'].split('\n')
            verified = form.cleaned_data['payment_verified']
            
            updated = 0
            for app_num in app_numbers:
                app_num = app_num.strip()
                if app_num:
                    try:
                        app = AdmissionApplication.objects.get(application_number=app_num)
                        app.payment_verified = verified
                        app.payment_verified_by = request.user.staff
                        app.payment_verified_date = timezone.now()
                        app.save()
                        updated += 1
                    except AdmissionApplication.DoesNotExist:
                        messages.warning(request, f"Application {app_num} not found")
            
            messages.success(request, f"Updated payment status for {updated} applications")
            return redirect('admissions:application_list')
    else:
        form = BulkPaymentVerificationForm()
    
    return render(request, 'admissions/bulk_verify.html', {'form': form})

@login_required
def payment_status_api(request, pk):
    """API endpoint to check payment status"""
    application = get_object_or_404(AdmissionApplication, pk=pk)
    
    return JsonResponse({
        'application_number': application.application_number,
        'payment_reference': application.payment_reference,
        'payment_verified': application.payment_verified,
        'payment_amount': str(application.payment_amount),
        'status': application.status,
    })

def application_submitted(request):
    """Thank you page after application submission"""
    return render(request, 'admissions/application_submitted.html')
    
    


class ReviewAdmissionApplicationView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Review an admission application"""
    model = AdmissionApplication
    form_class = AdmissionReviewForm
    template_name = 'admissions/application_review.html'
    permission_required = 'admissions.review_application'
    
    def form_valid(self, form):
        instance = form.save(commit=False)
        move_to_review = form.cleaned_data.get('move_to_review')
        
        if move_to_review:
            # Create review log
            AdmissionReviewLog.objects.create(
                application=instance,
                staff=self.request.user.staff,
                action='MOVED_TO_REVIEW',
                notes=instance.review_notes,
                from_status=instance.status,
                to_status=AdmissionApplication.ApplicationStatus.UNDER_REVIEW
            )
            
            # Update application
            instance.status = AdmissionApplication.ApplicationStatus.UNDER_REVIEW
            instance.reviewed_by = self.request.user.staff
            instance.review_date = timezone.now()
        
        instance.save()
        
        messages.success(self.request, _("Application review updated successfully"))
        return redirect('admissions:application_detail', pk=instance.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['review_logs'] = self.object.review_logs.all()[:10]
        return context

class AdmissionDecisionView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Make admission decision (approve/reject/waitlist)"""
    model = AdmissionApplication
    form_class = AdmissionDecisionForm
    template_name = 'admissions/application_decision.html'
    permission_required = 'admissions.make_admission_decision'
    
    def form_valid(self, form):
        instance = form.save(commit=False)
        decision = form.cleaned_data.get('decision')
        
        # Create decision log
        AdmissionReviewLog.objects.create(
            application=instance,
            staff=self.request.user.staff,
            action=f'{decision.upper()}_APPLICATION',
            notes=instance.decision_notes,
            from_status=instance.status,
            to_status=AdmissionApplication.ApplicationStatus.APPROVED if decision == 'approve' else
                     AdmissionApplication.ApplicationStatus.REJECTED if decision == 'reject' else
                     AdmissionApplication.ApplicationStatus.WAITLISTED
        )
        
        # Update application
        instance.decision_by = self.request.user.staff
        instance.decision_date = timezone.now()
        
        # If approved, send admission letter automatically
        if decision == 'approve':
            instance.admission_letter_sent = True
            instance.admission_letter_sent_date = timezone.now()
            
            # Send notification email (in background)
            self.send_admission_letter(instance)
        
        instance.save()
        
        action_word = 'approved' if decision == 'approve' else 'rejected' if decision == 'reject' else 'waitlisted'
        messages.success(self.request, _(f"Application has been {action_word}"))
        
        return redirect('admissions:application_detail', pk=instance.pk)
    
    def send_admission_letter(self, application):
        """Send admission letter email"""
        try:
            subject = f"Admission Offer - {application.admission_session} - {application.admission_class}"
            message = render_to_string('admissions/emails/admission_letter.txt', {
                'application': application,
                'school_name': settings.SCHOOL_NAME,
            })
            html_message = render_to_string('admissions/emails/admission_letter.html', {
                'application': application,
                'school_name': settings.SCHOOL_NAME,
            })
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.guardian_email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send admission letter: {e}")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['decision_logs'] = AdmissionReviewLog.objects.filter(
            application=self.object,
            action__in=['APPROVE_APPLICATION', 'REJECT_APPLICATION', 'WAITLIST_APPLICATION']
        )[:5]
        
        # Check class capacity
        if self.object.admission_class:
            current_count = Student.objects.filter(
                current_class=self.object.admission_class
            ).count()
            
            from apps.corecode.models import SiteConfig
            try:
                config = SiteConfig.objects.first()
                max_capacity = config.max_class_capacity if config else 40
                context['class_capacity'] = {
                    'current': current_count,
                    'max': max_capacity,
                    'available': max_capacity - current_count,
                    'is_full': current_count >= max_capacity
                }
            except:
                context['class_capacity'] = {'current': 0, 'max': 40, 'available': 40, 'is_full': False}
        
        return context

class WaitlistManagementView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Manage waitlisted applications"""
    model = AdmissionApplication
    form_class = WaitlistManagementForm
    template_name = 'admissions/waitlist_manage.html'
    permission_required = 'admissions.manage_waitlist'
    
    def form_valid(self, form):
        instance = form.save(commit=False)
        
        # Log the update
        AdmissionReviewLog.objects.create(
            application=instance,
            staff=self.request.user.staff,
            action='WAITLIST_UPDATE',
            notes=f"Waitlist position updated to {instance.waitlist_position}",
            from_status=instance.status,
            to_status=instance.status
        )
        
        instance.save()
        messages.success(self.request, _("Waitlist updated successfully"))
        return redirect('admissions:waitlist_dashboard')
    
    def get_success_url(self):
        return reverse_lazy('admissions:waitlist_dashboard')

@login_required
@permission_required('admissions.make_admission_decision', raise_exception=True)
def bulk_decision_view(request):
    """Bulk decision making for applications"""
    if request.method == 'POST':
        form = BulkDecisionForm(request.POST)
        if form.is_valid():
            applications = form.cleaned_data['applications']
            decision = form.cleaned_data['decision']
            decision_notes = form.cleaned_data['decision_notes']
            rejection_reason = form.cleaned_data.get('rejection_reason')
            
            updated_count = 0
            
            for application in applications:
                # Update application
                if decision == 'approve':
                    application.status = AdmissionApplication.ApplicationStatus.APPROVED
                elif decision == 'reject':
                    application.status = AdmissionApplication.ApplicationStatus.REJECTED
                    application.rejection_reason = rejection_reason
                elif decision == 'waitlist':
                    application.status = AdmissionApplication.ApplicationStatus.WAITLISTED
                
                application.decision_by = request.user.staff
                application.decision_date = timezone.now()
                application.decision_notes = decision_notes
                application.save()
                
                # Create log
                AdmissionReviewLog.objects.create(
                    application=application,
                    staff=request.user.staff,
                    action=f'BULK_{decision.upper()}',
                    notes=decision_notes,
                    from_status=AdmissionApplication.ApplicationStatus.UNDER_REVIEW,
                    to_status=application.status
                )
                
                updated_count += 1
            
            messages.success(request, _(f"Updated {updated_count} applications"))
            return redirect('admissions:application_list')
    else:
        form = BulkDecisionForm()
    
    return render(request, 'admissions/bulk_decision.html', {'form': form})

@login_required
@permission_required('admissions.manage_waitlist', raise_exception=True)
def waitlist_dashboard(request):
    """Dashboard for waitlist management"""
    waitlisted = AdmissionApplication.objects.filter(
        status=AdmissionApplication.ApplicationStatus.WAITLISTED
    ).order_by('waitlist_position')
    
    # Get class capacities
    from apps.corecode.models import StudentClass
    classes = StudentClass.objects.all()
    class_capacities = []
    
    for cls in classes:
        current = Student.objects.filter(current_class=cls).count()
        waitlisted_count = AdmissionApplication.objects.filter(
            status=AdmissionApplication.ApplicationStatus.WAITLISTED,
            admission_class=cls
        ).count()
        
        from apps.corecode.models import SiteConfig
        try:
            config = SiteConfig.objects.first()
            max_capacity = config.max_class_capacity if config else 40
        except:
            max_capacity = 40
        
        class_capacities.append({
            'class': cls,
            'current': current,
            'waitlisted': waitlisted_count,
            'max': max_capacity,
            'available': max_capacity - current,
        })
    
    return render(request, 'admissions/waitlist_dashboard.html', {
        'waitlisted': waitlisted,
        'class_capacities': class_capacities,
    })

@login_required
@permission_required('admissions.make_admission_decision', raise_exception=True)
def send_admission_letter_view(request, pk):
    """Send admission letter to guardian"""
    application = get_object_or_404(AdmissionApplication, pk=pk)
    
    if application.status != AdmissionApplication.ApplicationStatus.APPROVED:
        messages.error(request, _("Can only send admission letters for approved applications"))
        return redirect('admissions:application_detail', pk=pk)
    
    if request.method == 'POST':
        form = SendAdmissionLetterForm(request.POST)
        if form.is_valid():
            # Update application
            application.admission_letter_sent = True
            application.admission_letter_sent_date = timezone.now()
            application.save()
            
            # Send email
            try:
                subject = f"Admission Offer - {application.admission_session} - {application.admission_class}"
                context = {
                    'application': application,
                    'school_name': settings.SCHOOL_NAME,
                    'include_fee_structure': form.cleaned_data['include_fee_structure'],
                    'include_payment_instructions': form.cleaned_data['include_payment_instructions'],
                    'custom_message': form.cleaned_data['custom_message'],
                }
                
                message = render_to_string('admissions/emails/admission_letter.txt', context)
                html_message = render_to_string('admissions/emails/admission_letter.html', context)
                
                recipient_list = [application.guardian_email]
                if form.cleaned_data['send_copy_to_guardian']:
                    # Could add additional guardian emails here
                    pass
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    html_message=html_message,
                    fail_silently=False,
                )
                
                # Log the action
                AdmissionReviewLog.objects.create(
                    application=application,
                    staff=request.user.staff,
                    action='SENT_ADMISSION_LETTER',
                    notes='Admission letter sent to guardian',
                    from_status=application.status,
                    to_status=application.status
                )
                
                messages.success(request, _("Admission letter sent successfully"))
            except Exception as e:
                messages.error(request, _(f"Failed to send email: {str(e)}"))
            
            return redirect('admissions:application_detail', pk=pk)
    else:
        form = SendAdmissionLetterForm()
    
    return render(request, 'admissions/send_admission_letter.html', {
        'application': application,
        'form': form,
    })

@login_required
@permission_required('admissions.make_admission_decision', raise_exception=True)
def promote_from_waitlist(request, pk):
    """Promote application from waitlist to approved"""
    application = get_object_or_404(AdmissionApplication, pk=pk)
    
    if application.status != AdmissionApplication.ApplicationStatus.WAITLISTED:
        messages.error(request, _("Application is not on waitlist"))
        return redirect('admissions:application_detail', pk=pk)
    
    # Check class capacity
    if application.admission_class:
        current_count = Student.objects.filter(
            current_class=application.admission_class
        ).count()
        
        from apps.corecode.models import SiteConfig
        try:
            config = SiteConfig.objects.first()
            max_capacity = config.max_class_capacity if config else 40
            if current_count >= max_capacity:
                messages.error(request, _("Class is at full capacity"))
                return redirect('admissions:waitlist_dashboard')
        except:
            pass
    
    # Promote application
    application.status = AdmissionApplication.ApplicationStatus.APPROVED
    application.decision_by = request.user.staff
    application.decision_date = timezone.now()
    application.decision_notes = f"Promoted from waitlist (position {application.waitlist_position})"
    application.waitlist_position = None
    application.save()
    
    # Log the action
    AdmissionReviewLog.objects.create(
        application=application,
        staff=request.user.staff,
        action='PROMOTED_FROM_WAITLIST',
        notes='Promoted from waitlist to approved',
        from_status=AdmissionApplication.ApplicationStatus.WAITLISTED,
        to_status=AdmissionApplication.ApplicationStatus.APPROVED
    )
    
    messages.success(request, _("Application promoted from waitlist"))
    return redirect('admissions:application_detail', pk=pk)

def admission_dashboard(request):
    """Dashboard for admission statistics"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not request.user.has_perm('admissions.view_admissionapplication'):
        messages.error(request, _("You don't have permission to view the dashboard"))
        return redirect('index')
    
    # Statistics
    total = AdmissionApplication.objects.count()
    
    status_counts = AdmissionApplication.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    payment_stats = {
        'verified': AdmissionApplication.objects.filter(payment_verified=True).count(),
        'unverified': AdmissionApplication.objects.filter(
            Q(payment_reference__isnull=False) | Q(payment_reference=''),
            payment_verified=False
        ).count(),
        'unpaid': AdmissionApplication.objects.filter(payment_reference='').count(),
    }
    
    # Recent activity
    recent_logs = AdmissionReviewLog.objects.select_related(
        'application', 'staff'
    ).order_by('-created_at')[:10]
    
    # Applications needing attention
    needs_review = AdmissionApplication.objects.filter(
        status=AdmissionApplication.ApplicationStatus.PENDING,
        payment_verified=True
    ).count()
    
    needs_decision = AdmissionApplication.objects.filter(
        status=AdmissionApplication.ApplicationStatus.UNDER_REVIEW
    ).count()
    
    return render(request, 'admissions/dashboard.html', {
        'total_applications': total,
        'status_counts': status_counts,
        'payment_stats': payment_stats,
        'recent_logs': recent_logs,
        'needs_review': needs_review,
        'needs_decision': needs_decision,
    })
    
    


class CreateStudentFromApplicationView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Create student from a single application"""
    permission_required = 'students.add_student'
    
    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        
        if not application.can_create_student:
            messages.error(request, _("Cannot create student from this application"))
            return redirect('admissions:application_detail', pk=pk)
        
        try:
            student = StudentCreationService.create_student_from_application(
                pk, request.user.staff
            )
            messages.success(
                request, 
                _(f"Student created successfully: {student.student_number}")
            )
        except StudentCreationError as e:
            messages.error(request, str(e))
        
        return redirect('admissions:application_detail', pk=pk)

@login_required
@permission_required('students.add_student', raise_exception=True)
def bulk_create_students_view(request):
    """Bulk create students from approved applications"""
    if request.method == 'POST':
        form = BulkCreateStudentsForm(request.POST)
        if form.is_valid():
            applications = form.cleaned_data['applications']
            auto_activate = form.cleaned_data['auto_activate']
            
            results = StudentCreationService.bulk_create_students(
                [app.pk for app in applications],
                request.user.staff
            )
            
            # Auto-activate if requested
            if auto_activate and results['success'] > 0:
                # Get the created students
                created_students = []
                for app in applications:
                    if hasattr(app, 'created_student'):
                        created_students.append(app.created_student.pk)
                
                if created_students:
                    activation_results = StudentActivationService.bulk_activate_students(
                        created_students, request.user.staff
                    )
                    results['activation'] = activation_results
            
            # Show results
            if results['success'] > 0:
                messages.success(
                    request, 
                    _(f"Successfully created {results['success']} students")
                )
            if results['failed'] > 0:
                messages.warning(
                    request, 
                    _(f"Failed to create {results['failed']} students")
                )
                for error in results['errors'][:5]:  # Show first 5 errors
                    messages.error(request, f"App {error['application_id']}: {error['error']}")
            
            return redirect('admissions:student_creation_dashboard')
    else:
        form = BulkCreateStudentsForm()
    
    return render(request, 'admissions/bulk_create_students.html', {'form': form})

class ManualStudentCreationView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create student manually"""
    model = Student
    form_class = CreateStudentForm
    template_name = 'admissions/manual_student_create.html'
    permission_required = 'students.add_student'
    success_url = reverse_lazy('admissions:student_creation_dashboard')
    
    def form_valid(self, form):
        try:
            from .services import ManualStudentCreationService
            
            # Get cleaned data
            data = form.cleaned_data.copy()
            
            # Add current user as creator
            data['created_by'] = self.request.user.staff
            
            # Create student using service
            student = ManualStudentCreationService.create_manual_student(
                data, self.request.user.staff
            )
            
            messages.success(
                self.request,
                _(f"Student created successfully: {student.student_number}")
            )
            
            return redirect('admissions:student_detail', pk=student.pk)
            
        except StudentCreationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Create Student Manually")
        return context

class StudentActivationView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Activate a student"""
    model = Student
    form_class = StudentActivationForm
    template_name = 'admissions/student_activate.html'
    permission_required = 'students.activate_student'
    
    def form_valid(self, form):
        instance = form.save(commit=False)
        
        try:
            # Activate the student
            StudentCreationService.activate_student(
                instance.pk, self.request.user.staff
            )
            
            messages.success(
                self.request,
                _(f"Student {instance.student_number} activated successfully")
            )
            
            return redirect('admissions:student_detail', pk=instance.pk)
            
        except StudentCreationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['missing_requirements'] = self.object.get_activation_requirements()
        return context

@login_required
@permission_required('students.activate_student', raise_exception=True)
def bulk_activate_students_view(request):
    """Bulk activate students"""
    if request.method == 'POST':
        form = BulkActivationForm(request.POST)
        if form.is_valid():
            students = form.cleaned_data['students']
            
            results = StudentActivationService.bulk_activate_students(
                [student.pk for student in students],
                request.user.staff
            )
            
            # Show results
            if results['success'] > 0:
                messages.success(
                    request, 
                    _(f"Successfully activated {results['success']} students")
                )
            if results['failed'] > 0:
                messages.warning(
                    request, 
                    _(f"Failed to activate {results['failed']} students")
                )
                for error in results['errors'][:5]:
                    messages.error(request, f"Student {error['student_id']}: {error['error']}")
            
            return redirect('admissions:student_creation_dashboard')
    else:
        form = BulkActivationForm()
    
    return render(request, 'admissions/bulk_activate_students.html', {'form': form})

@login_required
def student_creation_dashboard(request):
    """Dashboard for student creation and activation"""
    if not request.user.has_perm('students.add_student'):
        messages.error(request, _("You don't have permission to view this page"))
        return redirect('index')
    
    # Statistics
    from .models import AdmissionApplication
    
    # Applications ready for student creation
    ready_applications = AdmissionApplication.objects.filter(
        status=AdmissionApplication.ApplicationStatus.APPROVED
    ).exclude(
        student__isnull=False
    ).filter(
        admission_class__isnull=False,
        admission_session__isnull=False
    ).count()
    
    # Students pending activation
    pending_activation = Student.objects.filter(
        status=Student.Status.INACTIVE
    ).count()
    
    # Recently created students
    recent_students = Student.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).order_by('-created_at')[:10]
    
    # Recently activated students
    recent_activations = Student.objects.filter(
        status=Student.Status.ACTIVE,
        updated_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).order_by('-updated_at')[:10]
    
    return render(request, 'admissions/student_creation_dashboard.html', {
        'ready_applications': ready_applications,
        'pending_activation': pending_activation,
        'recent_students': recent_students,
        'recent_activations': recent_activations,
    })

class StudentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View student details"""
    model = Student
    template_name = 'admissions/student_detail.html'
    permission_required = 'students.view_student'
    context_object_name = 'student'
    
    

class EnhancedManualStudentCreationView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Enhanced manual student creation with better UX"""
    form_class = EnhancedManualStudentForm
    template_name = 'admissions/enhanced_manual_create.html'
    permission_required = 'students.add_student'
    success_url = reverse_lazy('admissions:student_creation_dashboard')
    
    def form_valid(self, form):
        try:
            from .services import ManualStudentCreationService
            
            # Get form data
            data = form.cleaned_data.copy()
            data['created_by'] = self.request.user.staff
            
            # Handle guardian
            include_guardian = data.get('include_guardian', True)
            existing_guardian = data.get('existing_guardian')
            
            if existing_guardian:
                # Use existing guardian
                data['guardian'] = existing_guardian
            elif include_guardian:
                # Create new guardian
                guardian_data = {
                    'guardian_email': data.get('guardian_email'),
                    'guardian_phone': data.get('guardian_phone'),
                    'guardian_surname': data.get('guardian_surname'),
                    'guardian_firstname': data.get('guardian_firstname'),
                    'guardian_address': data.get('guardian_address', ''),
                    'guardian_relationship': data.get('guardian_relationship', 'Parent'),
                }
                data.update(guardian_data)
            
            # Auto-assign current session if requested
            if data.get('auto_assign_class'):
                from apps.corecode.models import AcademicSession
                try:
                    current_session = AcademicSession.objects.get(current=True)
                    data['current_session'] = current_session
                except AcademicSession.DoesNotExist:
                    pass
            
            # Create student using service
            student = ManualStudentCreationService.create_manual_student(
                data, self.request.user.staff
            )
            
            # Try to auto-activate if possible
            if student.is_activatable:
                try:
                    StudentCreationService.activate_student(
                        student.pk, self.request.user.staff
                    )
                    messages.success(
                        self.request,
                        _(f"Student {student.student_number} created and activated successfully!")
                    )
                except StudentCreationError:
                    messages.success(
                        self.request,
                        _(f"Student {student.student_number} created but needs activation")
                    )
            else:
                messages.success(
                    self.request,
                    _(f"Student {student.student_number} created. Needs guardian/class/session for activation.")
                )
            
            return redirect('admissions:student_detail', pk=student.pk)
            
        except StudentCreationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Create Student Manually")
        context['guardians'] = Guardian.objects.all().order_by('surname', 'firstname')[:50]  # Limit for dropdown
        
        # Get current session for default
        from apps.corecode.models import AcademicSession
        try:
            context['current_session'] = AcademicSession.objects.get(current=True)
        except AcademicSession.DoesNotExist:
            context['current_session'] = None
        
        return context

class QuickStudentCreationView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Quick/bulk student creation"""
    form_class = QuickStudentForm
    template_name = 'admissions/quick_student_create.html'
    permission_required = 'students.add_student'
    success_url = reverse_lazy('admissions:student_creation_dashboard')
    
    def form_valid(self, form):
        from .services import ManualStudentCreationService
        
        students_data = form.cleaned_data['students_data']
        common_guardian = form.cleaned_data.get('common_guardian')
        current_session = form.cleaned_data['current_session']
        
        created_count = 0
        failed_count = 0
        errors = []
        
        for student_data in students_data:
            try:
                # Prepare data for service
                data = {
                    'surname': student_data['surname'],
                    'firstname': student_data['firstname'],
                    'other_name': student_data.get('other_name', ''),
                    'gender': student_data['gender'],
                    'date_of_birth': student_data['date_of_birth'],
                    'current_class': student_data.get('current_class'),
                    'current_session': current_session,
                    'created_by': self.request.user.staff,
                }
                
                # Add guardian if provided
                if common_guardian:
                    data['guardian'] = common_guardian
                
                # Create student
                student = ManualStudentCreationService.create_manual_student(data, self.request.user.staff)
                created_count += 1
                
            except StudentCreationError as e:
                failed_count += 1
                errors.append(f"{student_data['raw_line']}: {str(e)}")
        
        # Show results
        if created_count > 0:
            messages.success(
                self.request,
                _(f"Successfully created {created_count} student(s)")
            )
        
        if failed_count > 0:
            messages.warning(
                self.request,
                _(f"Failed to create {failed_count} student(s)")
            )
            for error in errors[:5]:  # Show first 5 errors
                messages.error(self.request, error)
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Quick Student Creation")
        
        # Get current session for default
        from apps.corecode.models import AcademicSession
        try:
            context['current_session'] = AcademicSession.objects.get(current=True)
        except AcademicSession.DoesNotExist:
            context['current_session'] = None
        
        # Get sample data
        context['sample_data'] = '''Adeboye, Chinedu, Michael, Male, 2015-06-15, Primary 5
Bello, Fatima,, Female, 2016-03-22, Primary 4
Chukwu, Ibrahim, Adamu, Male, 2014-11-30, Primary 6'''
        
        return context

class StudentActivationWizardView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Wizard for activating multiple students"""
    form_class = StudentActivationForm
    template_name = 'admissions/student_activation_wizard.html'
    permission_required = 'students.activate_student'
    success_url = reverse_lazy('admissions:student_creation_dashboard')
    
    def form_valid(self, form):
        students = form.cleaned_data['students']
        assign_class = form.cleaned_data.get('assign_class')
        assign_session = form.cleaned_data['assign_session']
        
        activated_count = 0
        failed_count = 0
        errors = []
        
        for student in students:
            try:
                # Update student if needed
                update_needed = False
                
                if not student.current_class and assign_class:
                    student.current_class = assign_class
                    update_needed = True
                
                if not student.current_session:
                    student.current_session = assign_session
                    update_needed = True
                
                if update_needed:
                    student.save()
                
                # Activate student
                StudentCreationService.activate_student(
                    student.pk, self.request.user.staff
                )
                activated_count += 1
                
            except StudentCreationError as e:
                failed_count += 1
                errors.append(f"{student}: {str(e)}")
        
        # Show results
        if activated_count > 0:
            messages.success(
                self.request,
                _(f"Successfully activated {activated_count} student(s)")
            )
        
        if failed_count > 0:
            messages.warning(
                self.request,
                _(f"Failed to activate {failed_count} student(s)")
            )
            for error in errors[:5]:
                messages.error(self.request, error)
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get inactive students stats
        inactive_students = Student.objects.filter(status=Student.Status.INACTIVE)
        
        # Categorize by missing requirements
        students_by_issue = {
            'no_guardian': [],
            'no_class': [],
            'no_session': [],
            'ready': [],
        }
        
        for student in inactive_students.select_related('guardian', 'current_class', 'current_session'):
            missing = student.get_activation_requirements()
            
            if 'Guardian/Parent' in missing:
                students_by_issue['no_guardian'].append(student)
            elif 'Class' in missing:
                students_by_issue['no_class'].append(student)
            elif 'Academic Session' in missing:
                students_by_issue['no_session'].append(student)
            else:
                students_by_issue['ready'].append(student)
        
        context['students_by_issue'] = students_by_issue
        context['total_inactive'] = inactive_students.count()
        
        return context

class InactiveStudentsListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all inactive students with filtering options"""
    model = Student
    template_name = 'admissions/inactive_students_list.html'
    context_object_name = 'students'
    permission_required = 'students.view_student'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Student.objects.filter(status=Student.Status.INACTIVE)
        
        # Filters
        missing = self.request.GET.get('missing')
        if missing == 'guardian':
            queryset = queryset.filter(guardian__isnull=True)
        elif missing == 'class':
            queryset = queryset.filter(current_class__isnull=True)
        elif missing == 'session':
            queryset = queryset.filter(current_session__isnull=True)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(student_number__icontains=search) |
                Q(surname__icontains=search) |
                Q(firstname__icontains=search) |
                Q(other_name__icontains=search)
            )
        
        return queryset.select_related('guardian', 'current_class', 'current_session')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Counts for filters
        context['total_inactive'] = Student.objects.filter(status=Student.Status.INACTIVE).count()
        context['no_guardian'] = Student.objects.filter(
            status=Student.Status.INACTIVE,
            guardian__isnull=True
        ).count()
        context['no_class'] = Student.objects.filter(
            status=Student.Status.INACTIVE,
            current_class__isnull=True
        ).count()
        context['no_session'] = Student.objects.filter(
            status=Student.Status.INACTIVE,
            current_session__isnull=True
        ).count()
        
        return context

@login_required
@permission_required('students.change_student', raise_exception=True)
def bulk_update_students(request):
    """Bulk update students (assign class, session, guardian)"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('students')
        action = request.POST.get('action')
        
        if not student_ids:
            messages.error(request, _("No students selected"))
            return redirect('admissions:inactive_students')
        
        students = Student.objects.filter(
            pk__in=student_ids,
            status=Student.Status.INACTIVE
        )
        
        updated_count = 0
        
        if action == 'assign_class':
            class_id = request.POST.get('class_id')
            if class_id:
                from apps.corecode.models import StudentClass
                try:
                    student_class = StudentClass.objects.get(pk=class_id)
                    students.update(current_class=student_class)
                    updated_count = students.count()
                    messages.success(request, _(f"Assigned class to {updated_count} students"))
                except StudentClass.DoesNotExist:
                    messages.error(request, _("Class not found"))
        
        elif action == 'assign_session':
            session_id = request.POST.get('session_id')
            if session_id:
                from apps.corecode.models import AcademicSession
                try:
                    session = AcademicSession.objects.get(pk=session_id)
                    students.update(current_session=session)
                    updated_count = students.count()
                    messages.success(request, _(f"Assigned session to {updated_count} students"))
                except AcademicSession.DoesNotExist:
                    messages.error(request, _("Session not found"))
        
        elif action == 'assign_guardian':
            guardian_id = request.POST.get('guardian_id')
            if guardian_id:
                try:
                    guardian = Guardian.objects.get(pk=guardian_id)
                    students.update(guardian=guardian)
                    updated_count = students.count()
                    messages.success(request, _(f"Assigned guardian to {updated_count} students"))
                except Guardian.DoesNotExist:
                    messages.error(request, _("Guardian not found"))
        
        elif action == 'activate':
            # Try to activate selected students
            from .services import StudentActivationService
            results = StudentActivationService.bulk_activate_students(
                [s.pk for s in students], request.user.staff
            )
            
            if results['success'] > 0:
                messages.success(request, _(f"Activated {results['success']} students"))
            if results['failed'] > 0:
                messages.warning(request, _(f"Failed to activate {results['failed']} students"))
        
        return redirect('admissions:inactive_students')
    
    # GET request - show form
    from apps.corecode.models import StudentClass, AcademicSession
    
    classes = StudentClass.objects.all()
    sessions = AcademicSession.objects.all()
    guardians = Guardian.objects.all()
    
    return render(request, 'admissions/bulk_update_students.html', {
        'classes': classes,
        'sessions': sessions,
        'guardians': guardians,
    })