"""
Finance utilities for fee generation and payment processing
"""
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal

from apps.students.models import Student
from apps.corecode.models import StudentClass, AcademicSession, AcademicTerm
from .models import Invoice, FeeStructure, GuardianPaymentSummary

def generate_invoice_for_student(student_id, session_id, term_id, description, amount):
    """
    Generate invoice for a student
    
    Returns: Invoice object
    Raises: ValidationError if student cannot be invoiced
    """
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        raise ValidationError(_("Student not found"))
    
    # Check student activation status
    is_active, missing = student.check_activation_status()
    if not is_active:
        raise ValidationError(
            _("Cannot generate invoice for inactive student. Missing: %(missing)s") % {
                'missing': ', '.join(missing)
            }
        )
    
    # Get session and term
    try:
        session = AcademicSession.objects.get(pk=session_id)
        term = AcademicTerm.objects.get(pk=term_id)
    except (AcademicSession.DoesNotExist, AcademicTerm.DoesNotExist):
        raise ValidationError(_("Academic session or term not found"))
    
    # Validate student is in correct session
    if student.current_session != session:
        raise ValidationError(
            _("Student is not enrolled in the selected academic session")
        )
    
    # Calculate due date (30 days from now by default)
    due_date = timezone.now().date() + timezone.timedelta(days=30)
    
    # Create invoice
    invoice = Invoice.objects.create(
        student=student,
        guardian=student.guardian,
        session=session,
        term=term,
        description=description,
        total_amount=amount,
        due_date=due_date,
        status='active'
    )
    
    return invoice

def generate_bulk_invoices(class_id, session_id, term_id, description_template, amount):
    """
    Generate invoices for all active students in a class
    
    Returns: (success_count, failed_count, errors)
    """
    try:
        student_class = StudentClass.objects.get(pk=class_id)
        session = AcademicSession.objects.get(pk=session_id)
        term = AcademicTerm.objects.get(pk=term_id)
    except (StudentClass.DoesNotExist, AcademicSession.DoesNotExist, AcademicTerm.DoesNotExist):
        raise ValidationError(_("Class, session, or term not found"))
    
    # Get active students in the class
    students = Student.get_active_students().filter(
        current_class=student_class,
        current_session=session
    )
    
    success_count = 0
    failed_count = 0
    errors = []
    
    with transaction.atomic():
        for student in students:
            try:
                description = description_template.format(
                    student=student.full_name,
                    class_name=student_class.name,
                    session=session.name,
                    term=term.name
                )
                
                generate_invoice_for_student(
                    student_id=student.id,
                    session_id=session.id,
                    term_id=term.id,
                    description=description,
                    amount=amount
                )
                
                success_count += 1
                
            except ValidationError as e:
                failed_count += 1
                errors.append(f"{student}: {str(e)}")
    
    return success_count, failed_count, errors

def generate_fees_from_structure(class_id, session_id, term_id):
    """
    Generate invoices from fee structure
    
    Returns: (success_count, failed_count, errors)
    """
    try:
        fee_structure = FeeStructure.objects.get(
            class_fee_id=class_id,
            session_id=session_id,
            term_id=term_id,
            is_active=True
        )
    except FeeStructure.DoesNotExist:
        raise ValidationError(_("Fee structure not found for selected class, session, and term"))
    
    # Get active students in the class
    students = Student.get_active_students().filter(
        current_class_id=class_id,
        current_session_id=session_id
    )
    
    success_count = 0
    failed_count = 0
    errors = []
    
    description = f"{fee_structure.class_fee} - {fee_structure.session} - {fee_structure.term} Fees"
    
    with transaction.atomic():
        for student in students:
            try:
                # Check if invoice already exists
                existing = Invoice.objects.filter(
                    student=student,
                    session=fee_structure.session,
                    term=fee_structure.term
                ).exists()
                
                if not existing:
                    generate_invoice_for_student(
                        student_id=student.id,
                        session_id=fee_structure.session.id,
                        term_id=fee_structure.term.id,
                        description=description,
                        amount=fee_structure.total_fee
                    )
                    
                    success_count += 1
                else:
                    errors.append(f"{student}: Invoice already exists")
                    failed_count += 1
                    
            except ValidationError as e:
                failed_count += 1
                errors.append(f"{student}: {str(e)}")
    
    return success_count, failed_count, errors

def get_guardian_financial_summary(guardian_id):
    """
    Get financial summary for a guardian
    
    Returns: dict with financial summary
    """
    try:
        guardian = Guardian.objects.get(pk=guardian_id)
    except Guardian.DoesNotExist:
        raise ValidationError(_("Guardian not found"))
    
    # Get or create summary
    summary, _ = GuardianPaymentSummary.objects.get_or_create(guardian=guardian)
    summary.update_summary()  # Ensure it's up to date
    
    # Get recent invoices
    recent_invoices = guardian.invoices.all().order_by('-issue_date')[:10]
    
    # Get recent payments
    recent_payments = Receipt.objects.filter(
        invoice__guardian=guardian
    ).order_by('-date_paid')[:10]
    
    # Get overdue invoices
    overdue_invoices = guardian.invoices.filter(
        status='overdue'
    ).order_by('due_date')
    
    # Get students under this guardian
    students = guardian.students.all()
    
    return {
        'guardian': guardian,
        'summary': summary,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'overdue_invoices': overdue_invoices,
        'students': students,
        'total_students': students.count(),
        'active_students': students.filter(status='active').count(),
    }

def process_partial_payment(invoice_id, amount, method='cash', notes=''):
    """
    Process partial payment for an invoice
    
    Returns: Receipt object
    Raises: ValidationError if payment cannot be processed
    """
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
    except Invoice.DoesNotExist:
        raise ValidationError(_("Invoice not found"))
    
    if amount <= 0:
        raise ValidationError(_("Payment amount must be positive"))
    
    if amount > invoice.balance:
        raise ValidationError(_("Payment amount exceeds outstanding balance"))
    
    # Create receipt
    from .models import Receipt
    receipt = Receipt.objects.create(
        invoice=invoice,
        amount_paid=amount,
        payment_method=method,
        notes=notes,
        date_paid=timezone.now().date()
    )
    
    # Update invoice
    invoice.amount_paid += amount
    invoice.save()
    
    return receipt

def generate_financial_report(start_date, end_date, guardian_id=None, class_id=None):
    """
    Generate financial report for a period
    
    Returns: dict with report data
    """
    invoices = Invoice.objects.filter(
        issue_date__gte=start_date,
        issue_date__lte=end_date
    )
    
    if guardian_id:
        invoices = invoices.filter(guardian_id=guardian_id)
    
    if class_id:
        invoices = invoices.filter(student__current_class_id=class_id)
    
    # Calculate totals
    total_invoiced = sum(inv.total_amount for inv in invoices)
    total_paid = sum(inv.amount_paid for inv in invoices)
    total_balance = sum(inv.balance for inv in invoices)
    
    # Counts by status
    status_counts = {}
    for status_code, status_name in Invoice.STATUS_CHOICES:
        count = invoices.filter(status=status_code).count()
        if count > 0:
            status_counts[status_name] = count
    
    # Payments in period
    payments = Receipt.objects.filter(
        date_paid__gte=start_date,
        date_paid__lte=end_date
    )
    
    if guardian_id:
        payments = payments.filter(invoice__guardian_id=guardian_id)
    
    total_payments = sum(p.amount_paid for p in payments)
    
    return {
        'period': {
            'start': start_date,
            'end': end_date,
        },
        'invoices': {
            'total': invoices.count(),
            'total_amount': total_invoiced,
            'paid_amount': total_paid,
            'balance_amount': total_balance,
            'status_counts': status_counts,
        },
        'payments': {
            'total': payments.count(),
            'total_amount': total_payments,
        },
        'invoices_list': invoices.order_by('-issue_date')[:100],  # Limit for display
        'payments_list': payments.order_by('-date_paid')[:100],
    }