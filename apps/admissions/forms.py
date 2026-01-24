from django import forms
from django.utils.translation import gettext_lazy as _
import datetime
from .models import AdmissionApplication, AdmissionReviewLog



class AdmissionApplicationForm(forms.ModelForm):
    """Form for submitting admission applications"""
    
    class Meta:
        model = AdmissionApplication
        fields = [
            'admission_session', 'admission_class',
            'guardian_name', 'guardian_email', 'guardian_phone', 
            'guardian_address', 'guardian_relationship',
            'first_name', 'middle_name', 'surname', 'gender',
            'date_of_birth', 'birth_certificate_number', 'religion',
            'previous_school', 'previous_class',
            'medical_conditions', 'allergies',
            'doctor_name', 'doctor_phone',
            'guardian_photo', 'student_photo', 'last_report_card',
            # PHASE 2: Payment fields
            'payment_reference', 'payment_channel', 'payment_receipt'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'guardian_address': forms.Textarea(attrs={'rows': 3}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'payment_reference': forms.TextInput(attrs={
                'placeholder': 'Enter payment reference (RRR/bank teller)',
                'class': 'payment-reference'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set payment amount based on school policy
        self.fields['payment_amount'] = forms.DecimalField(
            initial=5000.00,  # Default application fee
            disabled=True,
            help_text=_("Application fee (non-refundable)")
        )
    
    def clean_date_of_birth(self):
        """Validate date of birth"""
        dob = self.cleaned_data['date_of_birth']
        if dob > datetime.date.today():
            raise forms.ValidationError(_("Date of birth cannot be in the future"))
        
        # Check minimum age (3 years)
        age = datetime.date.today().year - dob.year
        if age < 3:
            raise forms.ValidationError(_("Student must be at least 3 years old"))
        
        return dob
    
    def clean_guardian_phone(self):
        """Validate Nigerian phone number"""
        phone = self.cleaned_data['guardian_phone']
        # Basic Nigerian phone validation
        phone = phone.replace(' ', '').replace('-', '')
        if not phone.startswith(('+234', '234', '0')):
            if len(phone) == 10:
                phone = '0' + phone
            else:
                raise forms.ValidationError(_("Please enter a valid Nigerian phone number"))
        
        # Remove country code for storage
        if phone.startswith('+234'):
            phone = '0' + phone[4:]
        elif phone.startswith('234'):
            phone = '0' + phone[3:]
        
        if len(phone) != 11:
            raise forms.ValidationError(_("Phone number must be 11 digits"))
        
        if not phone.startswith(('070', '080', '081', '090', '091')):
            raise forms.ValidationError(_("Please enter a valid Nigerian network number"))
        
        return phone

class PaymentVerificationForm(forms.ModelForm):
    """Form for verifying payment references"""
    
    class Meta:
        model = AdmissionApplication
        fields = [
            'payment_reference', 
            'payment_verified', 
            'payment_amount',
            'payment_channel',
            'payment_verified_by',
            'payment_verified_date',
            'payment_receipt'
        ]
        widgets = {
            'payment_reference': forms.TextInput(attrs={
                'placeholder': 'Enter payment reference (RRR)',
                'class': 'form-control'
            }),
            'payment_verified_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_verified_by'].disabled = True
        self.fields['payment_verified_date'].disabled = True
        
        if self.instance and self.instance.payment_verified:
            self.fields['payment_reference'].disabled = True

class AdmissionReviewForm(forms.ModelForm):
    """Form for reviewing admission applications"""
    
    class Meta:
        model = AdmissionApplication
        fields = ['review_notes', 'status']
        widgets = {
            'review_notes': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        review_notes = cleaned_data.get('review_notes')
        
        if status == AdmissionApplication.ApplicationStatus.UNDER_REVIEW:
            if not review_notes:
                raise forms.ValidationError(_("Review notes are required when moving to review"))
            if not self.instance.payment_verified:
                raise forms.ValidationError(_("Cannot review application without verified payment"))
        
        return cleaned_data

class BulkPaymentVerificationForm(forms.Form):
    """Form for bulk verification of payments"""
    application_numbers = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Enter application numbers, one per line\nAPP-202401-0001\nAPP-202401-0002'
        }),
        help_text=_("Enter one application number per line")
    )
    payment_verified = forms.BooleanField(
        initial=True,
        required=False,
        help_text=_("Check to verify payments, uncheck to mark as unverified")
    )
    




class AdmissionReviewForm(forms.ModelForm):
    """Form for reviewing admission applications"""
    
    move_to_review = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Move to Review"),
        help_text=_("Check to move application from Pending to Under Review")
    )
    
    class Meta:
        model = AdmissionApplication
        fields = ['review_notes']
        widgets = {
            'review_notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('Enter detailed review notes...')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status != AdmissionApplication.ApplicationStatus.PENDING:
            self.fields['move_to_review'].widget = forms.HiddenInput()
            self.fields['move_to_review'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        move_to_review = cleaned_data.get('move_to_review')
        review_notes = cleaned_data.get('review_notes')
        
        if move_to_review:
            if not self.instance.payment_verified:
                raise forms.ValidationError(_("Cannot review application without verified payment"))
            if not review_notes:
                raise forms.ValidationError(_("Review notes are required when moving to review"))
        
        return cleaned_data

class AdmissionDecisionForm(forms.ModelForm):
    """Form for making admission decisions (approve/reject/waitlist)"""
    
    DECISION_CHOICES = [
        ('approve', _('Approve Application')),
        ('reject', _('Reject Application')),
        ('waitlist', _('Waitlist Application')),
    ]
    
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect,
        label=_("Decision")
    )
    
    class Meta:
        model = AdmissionApplication
        fields = ['decision_notes', 'rejection_reason', 'rejection_details', 'waitlist_notes']
        widgets = {
            'decision_notes': forms.Textarea(attrs={'rows': 4}),
            'rejection_details': forms.Textarea(attrs={'rows': 3}),
            'waitlist_notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show/hide fields based on decision
        self.fields['rejection_reason'].required = False
        self.fields['rejection_details'].required = False
        self.fields['waitlist_notes'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        rejection_reason = cleaned_data.get('rejection_reason')
        rejection_details = cleaned_data.get('rejection_details')
        
        if decision == 'reject':
            if not rejection_reason:
                self.add_error('rejection_reason', _("Rejection reason is required"))
            if not cleaned_data.get('decision_notes'):
                self.add_error('decision_notes', _("Decision notes are required for rejection"))
        
        elif decision == 'approve' and not cleaned_data.get('decision_notes'):
            self.add_error('decision_notes', _("Decision notes are required for approval"))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        decision = self.cleaned_data.get('decision')
        
        if decision == 'approve':
            instance.status = AdmissionApplication.ApplicationStatus.APPROVED
        elif decision == 'reject':
            instance.status = AdmissionApplication.ApplicationStatus.REJECTED
        elif decision == 'waitlist':
            instance.status = AdmissionApplication.ApplicationStatus.WAITLISTED
        
        if commit:
            instance.save()
        
        return instance

class BulkDecisionForm(forms.Form):
    """Form for bulk decisions"""
    
    applications = forms.ModelMultipleChoiceField(
        queryset=AdmissionApplication.objects.filter(
            status=AdmissionApplication.ApplicationStatus.UNDER_REVIEW
        ),
        widget=forms.CheckboxSelectMultiple,
        label=_("Select Applications")
    )
    
    decision = forms.ChoiceField(
        choices=[
            ('approve', _('Approve Selected')),
            ('reject', _('Reject Selected')),
            ('waitlist', _('Waitlist Selected')),
        ],
        label=_("Bulk Decision")
    )
    
    decision_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label=_("Decision Notes (applied to all)")
    )
    
    rejection_reason = forms.ChoiceField(
        choices=AdmissionApplication._meta.get_field('rejection_reason').choices,
        required=False,
        label=_("Rejection Reason")
    )

class WaitlistManagementForm(forms.ModelForm):
    """Form for managing waitlisted applications"""
    
    class Meta:
        model = AdmissionApplication
        fields = ['waitlist_position', 'waitlist_notes']
        widgets = {
            'waitlist_notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_waitlist_position(self):
        position = self.cleaned_data['waitlist_position']
        
        if position:
            # Check if position is already taken
            existing = AdmissionApplication.objects.filter(
                status=AdmissionApplication.ApplicationStatus.WAITLISTED,
                waitlist_position=position
            ).exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    _("Waitlist position {} is already taken").format(position)
                )
        
        return position

class SendAdmissionLetterForm(forms.Form):
    """Form for sending admission letters"""
    
    include_fee_structure = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Include Fee Structure")
    )
    
    include_payment_instructions = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Include Payment Instructions")
    )
    
    custom_message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        label=_("Custom Message")
    )
    
    send_copy_to_guardian = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Send copy to guardian email")
    )