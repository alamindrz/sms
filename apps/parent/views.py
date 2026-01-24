from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, UpdateView
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg, Max
from django.http import JsonResponse

from apps.students.models import Guardian, Student
from apps.result.models import Result
from apps.finance.models import Invoice, Receipt
from .models import ParentNotification, StudentProgress
from .forms import ParentProfileForm, ParentPasswordChangeForm, ContactSchoolForm

class ParentLoginRequiredMixin(LoginRequiredMixin):
    """Mixin to ensure user is a parent/guardian"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Check if user is a guardian
        if not hasattr(request.user, 'guardian_profile'):
            messages.error(request, _("Access denied. Parent portal only."))
            return redirect('index')
        
        return super().dispatch(request, *args, **kwargs)

class ParentDashboardView(ParentLoginRequiredMixin, TemplateView):
    """Parent dashboard"""
    template_name = 'parent/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.request.user.guardian_profile
        
        # Get guardian's wards
        wards = guardian.students.all()
        
        # Get recent notifications
        notifications = ParentNotification.objects.filter(
            guardian=guardian
        ).order_by('-created_at')[:10]
        
        # Get upcoming fee due dates
        upcoming_fees = Invoice.objects.filter(
            student__in=wards,
            status__in=['active', 'partially_paid'],
            due_date__gte=timezone.now().date()
        ).order_by('due_date')[:5]
        
        # Get recent results
        recent_results = Result.objects.filter(
            student__in=wards
        ).order_by('-date_created')[:5]
        
        # Get unread notification count
        unread_count = ParentNotification.objects.filter(
            guardian=guardian,
            is_read=False
        ).count()
        
        context.update({
            'guardian': guardian,
            'wards': wards,
            'notifications': notifications,
            'upcoming_fees': upcoming_fees,
            'recent_results': recent_results,
            'unread_count': unread_count,
            'total_wards': wards.count(),
            'active_wards': wards.filter(status='active').count(),
        })
        
        return context

class MyWardsView(ParentLoginRequiredMixin, ListView):
    """View all wards/students"""
    template_name = 'parent/my_wards.html'
    context_object_name = 'wards'
    
    def get_queryset(self):
        guardian = self.request.user.guardian_profile
        return guardian.students.all().select_related(
            'current_class', 'current_session'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.request.user.guardian_profile
        
        # Calculate some statistics
        wards = self.get_queryset()
        context['active_wards'] = wards.filter(status='active')
        context['inactive_wards'] = wards.filter(status='inactive')
        
        return context

class WardDetailView(ParentLoginRequiredMixin, DetailView):
    """View details of a specific ward"""
    template_name = 'parent/ward_detail.html'
    context_object_name = 'student'
    
    def get_queryset(self):
        guardian = self.request.user.guardian_profile
        return guardian.students.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        
        # Get academic information
        context['results'] = Result.objects.filter(
            student=student
        ).order_by('-session', '-term__name')
        
        # Get fee information
        context['invoices'] = Invoice.objects.filter(
            student=student
        ).order_by('-due_date')
        
        # Calculate fee summary
        total_invoices = Invoice.objects.filter(student=student)
        if total_invoices.exists():
            context['total_fees'] = sum(inv.balance for inv in total_invoices)
            context['paid_fees'] = sum(inv.total_amount_paid for inv in total_invoices)
            context['outstanding_fees'] = sum(inv.balance for inv in total_invoices)
        
        # Get attendance (if you have attendance module)
        # context['attendance'] = Attendance.objects.filter(student=student)
        
        return context

class ResultsView(ParentLoginRequiredMixin, TemplateView):
    """View academic results"""
    template_name = 'parent/results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.request.user.guardian_profile
        
        # Get all wards
        wards = guardian.students.all()
        
        # Get results grouped by student
        student_results = {}
        for ward in wards:
            results = Result.objects.filter(
                student=ward
            ).select_related('session', 'term', 'subject').order_by('-session__name', 'term__name')
            
            if results.exists():
                student_results[ward] = results
        
        context['student_results'] = student_results
        
        # Get progress reports if available
        progress_reports = StudentProgress.objects.filter(
            student__in=wards
        ).select_related('student', 'term')
        
        context['progress_reports'] = progress_reports
        
        return context

class PaymentsView(ParentLoginRequiredMixin, TemplateView):
    """View fee payments"""
    template_name = 'parent/payments.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.request.user.guardian_profile
        
        # Get all invoices for wards
        wards = guardian.students.all()
        invoices = Invoice.objects.filter(
            student__in=wards
        ).select_related('student', 'session', 'term').order_by('-due_date')
        
        # Calculate summary
        total_due = sum(inv.balance for inv in invoices)
        total_paid = sum(inv.total_amount_paid for inv in invoices)
        total_invoiced = sum(inv.total_amount for inv in invoices)
        
        # Get receipts
        receipts = Receipt.objects.filter(
            invoice__student__in=wards
        ).select_related('invoice', 'invoice__student').order_by('-date_paid')
        
        # Get upcoming due dates
        upcoming = invoices.filter(
            due_date__gte=timezone.now().date(),
            balance__gt=0
        ).order_by('due_date')[:10]
        
        # Get overdue invoices
        overdue = invoices.filter(
            due_date__lt=timezone.now().date(),
            balance__gt=0
        ).order_by('due_date')
        
        context.update({
            'invoices': invoices,
            'receipts': receipts,
            'upcoming': upcoming,
            'overdue': overdue,
            'total_due': total_due,
            'total_paid': total_paid,
            'total_invoiced': total_invoiced,
            'wards': wards,
        })
        
        return context

class AttendanceView(ParentLoginRequiredMixin, TemplateView):
    """View attendance (placeholder - integrate with your attendance module)"""
    template_name = 'parent/attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add attendance data here when you have attendance module
        return context

class AnnouncementsView(ParentLoginRequiredMixin, ListView):
    """View announcements/notifications"""
    template_name = 'parent/announcements.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        guardian = self.request.user.guardian_profile
        return ParentNotification.objects.filter(
            guardian=guardian
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardian = self.request.user.guardian_profile
        
        # Mark notifications as read when viewed
        unread = ParentNotification.objects.filter(
            guardian=guardian,
            is_read=False
        )
        unread.update(is_read=True)
        
        # Get counts by type
        context['unread_count'] = unread.count()
        
        return context

class ProfileView(ParentLoginRequiredMixin, UpdateView):
    """Update parent profile"""
    template_name = 'parent/profile.html'
    form_class = ParentProfileForm
    success_url = reverse_lazy('parent:profile')
    
    def get_object(self):
        return self.request.user.guardian_profile
    
    def form_valid(self, form):
        messages.success(self.request, _("Profile updated successfully"))
        return super().form_valid(form)

class SettingsView(ParentLoginRequiredMixin, TemplateView):
    """Parent settings (password change, preferences)"""
    template_name = 'parent/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_form'] = ParentPasswordChangeForm(user=self.request.user)
        return context
    
    def post(self, request, *args, **kwargs):
        if 'change_password' in request.POST:
            form = ParentPasswordChangeForm(user=request.user, data=request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, _("Password changed successfully"))
                return redirect('parent:settings')
            else:
                context = self.get_context_data()
                context['password_form'] = form
                return self.render_to_response(context)
        
        return super().get(request, *args, **kwargs)

class ContactSchoolView(ParentLoginRequiredMixin, TemplateView):
    """Contact school form"""
    template_name = 'parent/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ContactSchoolForm()
        context['wards'] = self.request.user.guardian_profile.students.all()
        return context
    
    def post(self, request, *args, **kwargs):
        form = ContactSchoolForm(request.POST)
        if form.is_valid():
            guardian = request.user.guardian_profile
            
            # Get selected student if any
            student_id = request.POST.get('student')
            student = None
            if student_id:
                try:
                    student = guardian.students.get(pk=student_id)
                except Student.DoesNotExist:
                    pass
            
            # Send email
            form.send_email(guardian, student)
            
            messages.success(request, _("Your message has been sent to the school"))
            return redirect('parent:dashboard')
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)

# API Views for AJAX
@login_required
def mark_notification_read(request, pk):
    """Mark notification as read"""
    if not hasattr(request.user, 'guardian_profile'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    notification = get_object_or_404(
        ParentNotification,
        pk=pk,
        guardian=request.user.guardian_profile
    )
    
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'success': True})

@login_required
def get_ward_summary(request, student_id):
    """Get summary for a specific ward"""
    if not hasattr(request.user, 'guardian_profile'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        student = request.user.guardian_profile.students.get(pk=student_id)
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    
    # Get recent results
    recent_results = Result.objects.filter(
        student=student
    ).order_by('-date_created')[:5]
    
    # Get fee summary
    invoices = Invoice.objects.filter(student=student)
    total_due = sum(inv.balance for inv in invoices)
    total_paid = sum(inv.total_amount_paid for inv in invoices)
    
    data = {
        'student': {
            'id': student.id,
            'name': student.full_name,
            'number': student.student_number,
            'class': str(student.current_class) if student.current_class else '',
            'status': student.get_status_display(),
        },
        'academic': {
            'recent_results': [
                {
                    'subject': str(r.subject),
                    'score': r.test_score + r.exam_score,
                    'term': str(r.term),
                    'session': str(r.session),
                }
                for r in recent_results
            ],
        },
        'finance': {
            'total_due': float(total_due),
            'total_paid': float(total_paid),
            'outstanding': float(total_due),
        },
    }
    
    return JsonResponse(data)