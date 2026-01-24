from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
import csv

from .models import Invoice, Receipt, FeeStructure, GuardianPaymentSummary
from .forms import InvoiceForm, ReceiptForm, FeeStructureForm, BulkInvoiceForm, PartialPaymentForm
from .utils import (
    generate_invoice_for_student,
    generate_bulk_invoices,
    generate_fees_from_structure,
    get_guardian_financial_summary,
    process_partial_payment,
    generate_financial_report
)
from apps.students.models import Student, Guardian
from apps.corecode.models import StudentClass, AcademicSession, AcademicTerm

class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List invoices with filtering"""
    model = Invoice
    template_name = 'finance/invoice_list.html'
    permission_required = 'finance.view_invoice'
    paginate_by = 50
    context_object_name = 'invoices'
    
    def get_queryset(self):
        queryset = Invoice.objects.all().select_related(
            'student', 'guardian', 'session', 'term'
        ).order_by('-issue_date')
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        guardian_id = self.request.GET.get('guardian')
        if guardian_id:
            queryset = queryset.filter(guardian_id=guardian_id)
        
        class_id = self.request.GET.get('class')
        if class_id:
            queryset = queryset.filter(student__current_class_id=class_id)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(student__surname__icontains=search) |
                Q(student__firstname__icontains=search) |
                Q(guardian__surname__icontains=search) |
                Q(guardian__firstname__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get summary statistics
        all_invoices = Invoice.objects.all()
        
        context['total_invoices'] = all_invoices.count()
        context['total_amount'] = all_invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        context['total_paid'] = all_invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_balance'] = all_invoices.aggregate(Sum('balance'))['balance__sum'] or 0
        
        # Count by status
        status_counts = {}
        for status_code, status_name in Invoice.STATUS_CHOICES:
            count = all_invoices.filter(status=status_code).count()
            if count > 0:
                status_counts[status_name] = count
        
        context['status_counts'] = status_counts
        
        # Filter options
        context['guardians'] = Guardian.objects.all().order_by('surname')[:50]  # Limit for dropdown
        context['classes'] = StudentClass.objects.all()
        
        return context

class SafeInvoiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create invoice with safety checks"""
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/safe_invoice_create.html'
    permission_required = 'finance.add_invoice'
    success_url = reverse_lazy('finance:invoice_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Set created_by
        form.instance.created_by = self.request.user.staff
        
        # Validate student activation
        student = form.cleaned_data['student']
        is_active, missing = student.check_activation_status()
        
        if not is_active:
            messages.error(
                self.request,
                _(f"Cannot create invoice. Student is inactive. Missing: {', '.join(missing)}")
            )
            return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            _(f"Invoice {form.instance.invoice_number} created successfully")
        )
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get eligible students count
        context['eligible_students'] = Student.get_active_students().count()
        context['total_students'] = Student.objects.count()
        
        return context

class BulkInvoiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Create bulk invoices"""
    template_name = 'finance/bulk_invoice.html'
    permission_required = 'finance.add_invoice'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['form'] = BulkInvoiceForm()
        context['fee_structures'] = FeeStructure.objects.filter(is_active=True)
        context['classes'] = StudentClass.objects.all()
        context['sessions'] = AcademicSession.objects.all()
        context['terms'] = AcademicTerm.objects.all()
        
        return context
    
    def post(self, request, *args, **kwargs):
        form = BulkInvoiceForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            
            if action == 'from_structure':
                # Generate from fee structure
                class_id = form.cleaned_data['class_id']
                session_id = form.cleaned_data['session_id']
                term_id = form.cleaned_data['term_id']
                
                try:
                    success_count, failed_count, errors = generate_fees_from_structure(
                        class_id, session_id, term_id
                    )
                    
                    if success_count > 0:
                        messages.success(
                            request,
                            _(f"Generated {success_count} invoices from fee structure")
                        )
                    
                    if failed_count > 0:
                        messages.warning(
                            request,
                            _(f"Failed to generate {failed_count} invoices")
                        )
                        for error in errors[:5]:
                            messages.error(request, error)
                    
                except ValidationError as e:
                    messages.error(request, str(e))
            
            elif action == 'custom_bulk':
                # Generate custom bulk invoices
                class_id = form.cleaned_data['class_id']
                session_id = form.cleaned_data['session_id']
                term_id = form.cleaned_data['term_id']
                description = form.cleaned_data['description']
                amount = form.cleaned_data['amount']
                
                try:
                    success_count, failed_count, errors = generate_bulk_invoices(
                        class_id, session_id, term_id, description, amount
                    )
                    
                    if success_count > 0:
                        messages.success(
                            request,
                            _(f"Generated {success_count} invoices")
                        )
                    
                    if failed_count > 0:
                        messages.warning(
                            request,
                            _(f"Failed to generate {failed_count} invoices")
                        )
                        for error in errors[:5]:
                            messages.error(request, error)
                    
                except ValidationError as e:
                    messages.error(request, str(e))
        
        return redirect('finance:invoice_list')

class InvoiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View invoice details"""
    model = Invoice
    template_name = 'finance/invoice_detail.html'
    permission_required = 'finance.view_invoice'
    context_object_name = 'invoice'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get receipts for this invoice
        context['receipts'] = self.object.receipts.all().order_by('-date_paid')
        
        # Get partial payment form
        context['partial_payment_form'] = PartialPaymentForm()
        
        return context

@login_required
@permission_required('finance.add_receipt', raise_exception=True)
def add_partial_payment(request, invoice_id):
    """Add partial payment to invoice"""
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    if request.method == 'POST':
        form = PartialPaymentForm(request.POST)
        
        if form.is_valid():
            amount = form.cleaned_data['amount']
            method = form.cleaned_data['payment_method']
            notes = form.cleaned_data['notes']
            
            try:
                receipt = process_partial_payment(
                    invoice_id=invoice.id,
                    amount=amount,
                    method=method,
                    notes=notes
                )
                
                messages.success(
                    request,
                    _(f"Payment of ₦{amount:,.2f} recorded. Receipt: {receipt.receipt_number}")
                )
                
            except ValidationError as e:
                messages.error(request, str(e))
    
    return redirect('finance:invoice_detail', pk=invoice_id)

class GuardianFinancialView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View guardian financial summary"""
    model = Guardian
    template_name = 'finance/guardian_financial.html'
    permission_required = 'finance.view_invoice'
    context_object_name = 'guardian'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get financial summary
        summary = get_guardian_financial_summary(self.object.id)
        context.update(summary)
        
        return context

class FeeStructureListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List fee structures"""
    model = FeeStructure
    template_name = 'finance/fee_structure_list.html'
    permission_required = 'finance.view_feestructure'
    context_object_name = 'fee_structures'
    
    def get_queryset(self):
        return FeeStructure.objects.filter(is_active=True).select_related(
            'class_fee', 'session', 'term'
        ).order_by('session', 'term', 'class_fee')

class FeeStructureCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create fee structure"""
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = 'finance/fee_structure_form.html'
    permission_required = 'finance.add_feestructure'
    success_url = reverse_lazy('finance:fee_structure_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user.staff
        messages.success(self.request, _("Fee structure created successfully"))
        return super().form_valid(form)

class FinancialReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Generate financial reports"""
    template_name = 'finance/financial_report.html'
    permission_required = 'finance.view_invoice'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Default period (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        # Get report
        report = generate_financial_report(start_date, end_date)
        context.update(report)
        
        # Filter options
        context['guardians'] = Guardian.objects.all().order_by('surname')[:50]
        context['classes'] = StudentClass.objects.all()
        
        return context
    
    def post(self, request, *args, **kwargs):
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        guardian_id = request.POST.get('guardian')
        class_id = request.POST.get('class')
        
        if not start_date or not end_date:
            messages.error(request, _("Please select start and end dates"))
            return redirect('finance:financial_report')
        
        # Generate report with filters
        report = generate_financial_report(
            start_date=start_date,
            end_date=end_date,
            guardian_id=guardian_id,
            class_id=class_id
        )
        
        context = self.get_context_data()
        context.update(report)
        context['filters_applied'] = True
        
        return render(request, self.template_name, context)

@login_required
@permission_required('finance.view_invoice', raise_exception=True)
def export_financial_report(request):
    """Export financial report as CSV"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    guardian_id = request.GET.get('guardian')
    class_id = request.GET.get('class')
    
    if not start_date or not end_date:
        messages.error(request, _("Please select start and end dates"))
        return redirect('finance:financial_report')
    
    # Generate report
    report = generate_financial_report(
        start_date=start_date,
        end_date=end_date,
        guardian_id=guardian_id,
        class_id=class_id
    )
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="financial_report_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['Financial Report', f'{start_date} to {end_date}'])
    writer.writerow([])
    
    # Write summary
    writer.writerow(['Summary'])
    writer.writerow(['Total Invoices', report['invoices']['total']])
    writer.writerow(['Total Amount', f"₦{report['invoices']['total_amount']:,.2f}"])
    writer.writerow(['Amount Paid', f"₦{report['invoices']['paid_amount']:,.2f}"])
    writer.writerow(['Balance', f"₦{report['invoices']['balance_amount']:,.2f}"])
    writer.writerow(['Total Payments', report['payments']['total']])
    writer.writerow(['Payments Amount', f"₦{report['payments']['total_amount']:,.2f}"])
    writer.writerow([])
    
    # Write invoices
    writer.writerow(['Invoices'])
    writer.writerow(['Invoice Number', 'Student', 'Guardian', 'Issue Date', 'Due Date', 
                     'Total Amount', 'Amount Paid', 'Balance', 'Status'])
    
    for invoice in report['invoices_list']:
        writer.writerow([
            invoice.invoice_number,
            invoice.student.full_name,
            invoice.guardian.full_name if invoice.guardian else '',
            invoice.issue_date,
            invoice.due_date,
            f"₦{invoice.total_amount:,.2f}",
            f"₦{invoice.amount_paid:,.2f}",
            f"₦{invoice.balance:,.2f}",
            invoice.get_status_display(),
        ])
    
    return response

# AJAX endpoints
@login_required
@permission_required('finance.view_invoice', raise_exception=True)
def get_guardian_summary_ajax(request, guardian_id):
    """Get guardian financial summary (AJAX)"""
    try:
        summary = get_guardian_financial_summary(guardian_id)
        
        return JsonResponse({
            'success': True,
            'guardian': {
                'id': summary['guardian'].id,
                'name': summary['guardian'].full_name,
                'email': summary['guardian'].email,
                'phone': summary['guardian'].phone,
            },
            'summary': {
                'total_invoiced': float(summary['summary'].total_invoiced),
                'total_paid': float(summary['summary'].total_paid),
                'total_balance': float(summary['summary'].total_balance),
                'total_invoices': summary['summary'].total_invoices,
                'paid_invoices': summary['summary'].paid_invoices,
                'overdue_invoices': summary['summary'].overdue_invoices,
            },
            'students_count': summary['total_students'],
            'active_students_count': summary['active_students'],
        })
        
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@permission_required('finance.add_invoice', raise_exception=True)
def check_student_invoice_eligibility(request, student_id):
    """Check if student can be invoiced (AJAX)"""
    try:
        student = Student.objects.get(pk=student_id)
        is_active, missing = student.check_activation_status()
        
        if is_active:
            return JsonResponse({
                'success': True,
                'student': {
                    'id': student.id,
                    'name': student.full_name,
                    'number': student.student_number,
                    'class': str(student.current_class) if student.current_class else '',
                },
                'message': _('Student is eligible for invoicing')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': _(f'Student is inactive. Missing: {", ".join(missing)}')
            })
            
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Student not found')})