from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Invoice, Receipt, FeeStructure
from apps.students.models import Student, Guardian
from apps.corecode.models import StudentClass, AcademicSession, AcademicTerm

class InvoiceForm(forms.ModelForm):
    """Invoice form with validation"""
    
    class Meta:
        model = Invoice
        fields = ['student', 'session', 'term', 'description', 'total_amount', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter students to only active ones
        self.fields['student'].queryset = Student.get_active_students().order_by('surname', 'firstname')
        
        # Set default due date (30 days from now)
        if not self.instance.pk:
            self.fields['due_date'].initial = timezone.now().date() + timezone.timedelta(days=30)
        
        # Add help text
        self.fields['student'].help_text = _("Only active students are shown")
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        due_date = cleaned_data.get('due_date')
        
        if student:
            # Check student activation
            is_active, missing = student.check_activation_status()
            if not is_active:
                raise ValidationError(
                    _("Cannot create invoice for inactive student. Missing: %(missing)s") % {
                        'missing': ', '.join(missing)
                    }
                )
        
        if due_date and due_date < timezone.now().date():
            raise ValidationError(_("Due date cannot be in the past"))
        
        return cleaned_data

class ReceiptForm(forms.ModelForm):
    """Receipt form"""
    
    class Meta:
        model = Receipt
        fields = ['invoice', 'amount_paid', 'payment_method', 'date_paid', 'notes']
        widgets = {
            'date_paid': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['date_paid'].initial = timezone.now().date()
    
    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        amount_paid = cleaned_data.get('amount_paid')
        
        if invoice and amount_paid:
            if amount_paid > invoice.balance:
                raise ValidationError(
                    _("Amount paid (₦%(amount)s) exceeds invoice balance (₦%(balance)s)") % {
                        'amount': amount_paid,
                        'balance': invoice.balance
                    }
                )
        
        return cleaned_data

class FeeStructureForm(forms.ModelForm):
    """Fee structure form"""
    
    class Meta:
        model = FeeStructure
        fields = ['class_fee', 'session', 'term', 'tuition_fee', 'development_levy', 
                 'sports_fee', 'library_fee', 'laboratory_fee', 'other_fees', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order choices
        self.fields['class_fee'].queryset = StudentClass.objects.all().order_by('name')
        self.fields['session'].queryset = AcademicSession.objects.all().order_by('-name')
        self.fields['term'].queryset = AcademicTerm.objects.all().order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check if fee structure already exists
        class_fee = cleaned_data.get('class_fee')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        
        if class_fee and session and term:
            existing = FeeStructure.objects.filter(
                class_fee=class_fee,
                session=session,
                term=term,
                is_active=True
            ).exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    _("An active fee structure already exists for this class, session, and term")
                )
        
        return cleaned_data

class BulkInvoiceForm(forms.Form):
    """Form for bulk invoice generation"""
    
    ACTION_CHOICES = [
        ('from_structure', _('Generate from Fee Structure')),
        ('custom_bulk', _('Generate Custom Invoices')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect,
        label=_("Action")
    )
    
    class_id = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        label=_("Class")
    )
    
    session_id = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        label=_("Academic Session")
    )
    
    term_id = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        label=_("Term")
    )
    
    # For custom bulk
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': _('Invoice description template')}),
        label=_("Description Template"),
        help_text=_("Use {student}, {class_name}, {session}, {term} as variables")
    )
    
    amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label=_("Amount"),
        help_text=_("Amount for each invoice")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current session as default
        try:
            current_session = AcademicSession.objects.get(current=True)
            self.fields['session_id'].initial = current_session
        except AcademicSession.DoesNotExist:
            pass
        
        # Order classes
        self.fields['class_id'].queryset = StudentClass.objects.all().order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'custom_bulk':
            if not cleaned_data.get('description'):
                self.add_error('description', _("Description is required for custom invoices"))
            
            if not cleaned_data.get('amount') or cleaned_data['amount'] <= 0:
                self.add_error('amount', _("Valid amount is required"))
        
        return cleaned_data

class PartialPaymentForm(forms.Form):
    """Form for partial payments"""
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label=_("Amount"),
        help_text=_("Amount to pay")
    )
    
    payment_method = forms.ChoiceField(
        choices=Receipt._meta.get_field('payment_method').choices,
        label=_("Payment Method")
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        label=_("Notes")
    )
    
    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)
        
        if self.invoice:
            # Set max amount as invoice balance
            self.fields['amount'].widget.attrs['max'] = self.invoice.balance
            self.fields['amount'].help_text = _("Maximum: ₦%(max)s") % {'max': self.invoice.balance}
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if self.invoice and amount > self.invoice.balance:
            raise ValidationError(
                _("Amount exceeds invoice balance of ₦%(balance)s") % {
                    'balance': self.invoice.balance
                }
            )
        
        if amount <= 0:
            raise ValidationError(_("Amount must be positive"))
        
        return amount

class FinancialReportForm(forms.Form):
    """Form for financial reports"""
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_("Start Date")
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_("End Date")
    )
    
    guardian = forms.ModelChoiceField(
        queryset=Guardian.objects.all(),
        required=False,
        label=_("Guardian (optional)")
    )
    
    student_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        required=False,
        label=_("Class (optional)")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default dates (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        self.fields['start_date'].initial = start_date
        self.fields['end_date'].initial = end_date
        
        # Order choices
        self.fields['guardian'].queryset = Guardian.objects.all().order_by('surname')
        self.fields['student_class'].queryset = StudentClass.objects.all().order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError(_("Start date cannot be after end date"))
        
        return cleaned_data