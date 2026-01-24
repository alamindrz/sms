from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.students.models import Student, Guardian
from apps.corecode.models import AcademicSession, AcademicTerm

class Invoice(models.Model):
    """Invoice model with guardian integration"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
        ('partially_paid', 'Partially Paid'),
    ]
    
    # Invoice Information
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Invoice Number")
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_("Student")
    )
    guardian = models.ForeignKey(
        Guardian,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name=_("Guardian"),
        help_text=_("Auto-filled from student's guardian")
    )
    
    # Academic Information
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        verbose_name=_("Academic Session")
    )
    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        verbose_name=_("Academic Term")
    )
    
    # Fee Details
    description = models.TextField(verbose_name=_("Description"))
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Total Amount")
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Amount Paid")
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        verbose_name=_("Balance")
    )
    
    # Dates
    issue_date = models.DateField(default=timezone.now, verbose_name=_("Issue Date"))
    due_date = models.DateField(verbose_name=_("Due Date"))
    date_paid = models.DateField(null=True, blank=True, verbose_name=_("Date Paid"))
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status")
    )
    
    # Payment Method
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('bank_deposit', 'Bank Deposit'),
            ('pos', 'POS'),
            ('online', 'Online Payment'),
            ('remita', 'Remita'),
            ('cheque', 'Cheque'),
        ],
        verbose_name=_("Payment Method")
    )
    
    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By")
    )
    
    class Meta:
        ordering = ['-issue_date', '-created_at']
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
    
    def __str__(self):
        return f"{self.invoice_number} - {self.student}"
    
    def save(self, *args, **kwargs):
        # Generate invoice number if new
        if not self.invoice_number:
            year = timezone.now().year
            last_invoice = Invoice.objects.filter(
                invoice_number__startswith=f'INV-{year}'
            ).order_by('-invoice_number').first()
            
            new_num = 1
            if last_invoice and last_invoice.invoice_number:
                try:
                    last_num = int(last_invoice.invoice_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    pass
            
            self.invoice_number = f"INV-{year}-{new_num:05d}"
        
        # Auto-fill guardian from student
        if self.student and not self.guardian:
            self.guardian = self.student.guardian
        
        # Calculate balance
        self.balance = self.total_amount - self.amount_paid
        
        # Update status based on balance
        if self.balance <= 0:
            self.status = 'paid'
            if not self.date_paid:
                self.date_paid = timezone.now().date()
        elif self.amount_paid > 0:
            self.status = 'partially_paid'
        elif self.due_date < timezone.now().date():
            self.status = 'overdue'
        else:
            self.status = 'active'
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate invoice"""
        errors = {}
        
        # Check student activation status
        if self.student:
            is_active, missing = self.student.check_activation_status()
            if not is_active:
                errors['student'] = _(
                    "Cannot create invoice for inactive student. "
                    "Missing: %(missing)s"
                ) % {'missing': ', '.join(missing)}
        
        # Validate due date
        if self.due_date and self.due_date < self.issue_date:
            errors['due_date'] = _("Due date cannot be before issue date")
        
        # Validate amounts
        if self.amount_paid > self.total_amount:
            errors['amount_paid'] = _("Amount paid cannot exceed total amount")
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        return self.due_date < timezone.now().date() and self.balance > 0
    
    @property
    def days_overdue(self):
        """Get number of days overdue"""
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0
    
    @property
    def payment_progress(self):
        """Get payment progress percentage"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0
    
    def add_payment(self, amount, method='cash', notes=''):
        """Add payment to invoice"""
        from .models import Receipt
        
        if amount <= 0:
            raise ValidationError(_("Payment amount must be positive"))
        
        if amount > self.balance:
            raise ValidationError(_("Payment amount exceeds outstanding balance"))
        
        # Create receipt
        receipt = Receipt.objects.create(
            invoice=self,
            amount_paid=amount,
            payment_method=method,
            notes=notes,
            date_paid=timezone.now().date()
        )
        
        # Update invoice
        self.amount_paid += amount
        self.save()
        
        return receipt

class Receipt(models.Model):
    """Payment receipt model"""
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='receipts',
        verbose_name=_("Invoice")
    )
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Receipt Number")
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount Paid")
    )
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('bank_deposit', 'Bank Deposit'),
            ('pos', 'POS'),
            ('online', 'Online Payment'),
            ('remita', 'Remita'),
            ('cheque', 'Cheque'),
        ],
        verbose_name=_("Payment Method")
    )
    date_paid = models.DateField(default=timezone.now, verbose_name=_("Date Paid"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    
    # Payment verification
    verified = models.BooleanField(default=False, verbose_name=_("Verified"))
    verified_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_receipts',
        verbose_name=_("Verified By")
    )
    verified_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Verified Date"))
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By")
    )
    
    class Meta:
        ordering = ['-date_paid', '-created_at']
        verbose_name = _('Receipt')
        verbose_name_plural = _('Receipts')
    
    def __str__(self):
        return f"{self.receipt_number} - {self.invoice}"
    
    def save(self, *args, **kwargs):
        # Generate receipt number if new
        if not self.receipt_number:
            year = timezone.now().year
            last_receipt = Receipt.objects.filter(
                receipt_number__startswith=f'RCP-{year}'
            ).order_by('-receipt_number').first()
            
            new_num = 1
            if last_receipt and last_receipt.receipt_number:
                try:
                    last_num = int(last_receipt.receipt_number.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    pass
            
            self.receipt_number = f"RCP-{year}-{new_num:05d}"
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate receipt"""
        if self.amount_paid <= 0:
            raise ValidationError(_("Amount paid must be positive"))
        
        if self.amount_paid > self.invoice.balance:
            raise ValidationError(_("Amount paid exceeds invoice balance"))
        
        if self.verified and not self.verified_by:
            raise ValidationError(_("Verified by is required when marking as verified"))

class FeeStructure(models.Model):
    """Fee structure for classes"""
    
    class_fee = models.ForeignKey(
        'corecode.StudentClass',
        on_delete=models.CASCADE,
        related_name='fee_structures',
        verbose_name=_("Class")
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        verbose_name=_("Academic Session")
    )
    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        verbose_name=_("Term")
    )
    
    # Fee items
    tuition_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Tuition Fee")
    )
    development_levy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Development Levy")
    )
    sports_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Sports Fee")
    )
    library_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Library Fee")
    )
    laboratory_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Laboratory Fee")
    )
    other_fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Other Fees")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    
    # System fields
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'staffs.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created By")
    )
    
    class Meta:
        ordering = ['session', 'term', 'class_fee']
        unique_together = ['class_fee', 'session', 'term']
        verbose_name = _('Fee Structure')
        verbose_name_plural = _('Fee Structures')
    
    def __str__(self):
        return f"{self.class_fee} - {self.session} - {self.term}"
    
    @property
    def total_fee(self):
        """Calculate total fee"""
        return (
            self.tuition_fee +
            self.development_levy +
            self.sports_fee +
            self.library_fee +
            self.laboratory_fee +
            self.other_fees
        )

class GuardianPaymentSummary(models.Model):
    """Guardian payment summary for quick access"""
    
    guardian = models.OneToOneField(
        Guardian,
        on_delete=models.CASCADE,
        related_name='payment_summary',
        verbose_name=_("Guardian")
    )
    
    # Summary fields
    total_invoiced = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Total Invoiced")
    )
    total_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Total Paid")
    )
    total_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Total Balance")
    )
    
    # Counts
    total_invoices = models.IntegerField(default=0, verbose_name=_("Total Invoices"))
    paid_invoices = models.IntegerField(default=0, verbose_name=_("Paid Invoices"))
    overdue_invoices = models.IntegerField(default=0, verbose_name=_("Overdue Invoices"))
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    last_invoice_date = models.DateField(null=True, blank=True, verbose_name=_("Last Invoice Date"))
    last_payment_date = models.DateField(null=True, blank=True, verbose_name=_("Last Payment Date"))
    
    class Meta:
        verbose_name = _('Guardian Payment Summary')
        verbose_name_plural = _('Guardian Payment Summaries')
    
    def __str__(self):
        return f"{self.guardian} - Payment Summary"
    
    def update_summary(self):
        """Update summary from invoices"""
        invoices = self.guardian.invoices.all()
        
        self.total_invoices = invoices.count()
        self.total_invoiced = sum(inv.total_amount for inv in invoices)
        self.total_paid = sum(inv.amount_paid for inv in invoices)
        self.total_balance = sum(inv.balance for inv in invoices)
        
        self.paid_invoices = invoices.filter(status='paid').count()
        self.overdue_invoices = invoices.filter(status='overdue').count()
        
        # Get last dates
        last_invoice = invoices.order_by('-issue_date').first()
        if last_invoice:
            self.last_invoice_date = last_invoice.issue_date
        
        last_payment = Receipt.objects.filter(invoice__guardian=self.guardian).order_by('-date_paid').first()
        if last_payment:
            self.last_payment_date = last_payment.date_paid
        
        self.save()