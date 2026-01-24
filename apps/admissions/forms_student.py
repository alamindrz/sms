"""
Forms for student creation and activation
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.students.models import Student, Guardian
from apps.corecode.models import StudentClass, AcademicSession


from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.students.models import Student, Guardian
import re

class EnhancedManualStudentForm(forms.ModelForm):
    """Enhanced form for manual student creation"""
    
    # Basic Information
    surname = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': _('Enter surname'),
            'class': 'form-control',
            'autocomplete': 'family-name'
        })
    )
    
    firstname = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': _('Enter first name'),
            'class': 'form-control',
            'autocomplete': 'given-name'
        })
    )
    
    other_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': _('Enter other name (optional)'),
            'class': 'form-control',
            'autocomplete': 'additional-name'
        })
    )
    
    gender = forms.ChoiceField(
        choices=[('Male', 'Male'), ('Female', 'Female')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        })
    )
    
    # Contact Information
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': _('student@example.com'),
            'class': 'form-control',
            'autocomplete': 'email'
        })
    )
    
    mobile_number = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': _('08012345678'),
            'class': 'form-control',
            'autocomplete': 'tel'
        })
    )
    
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Enter residential address'),
            'class': 'form-control',
            'autocomplete': 'street-address'
        })
    )
    
    # Academic Information
    current_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    current_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Medical Information
    medical_conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': _('Any known medical conditions'),
            'class': 'form-control'
        })
    )
    
    allergies = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': _('Any known allergies'),
            'class': 'form-control'
        })
    )
    
    # Guardian Information Section
    include_guardian = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Include guardian information"),
        help_text=_("Student will be inactive without a guardian")
    )
    
    guardian_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': _('guardian@example.com'),
            'class': 'form-control guardian-field',
            'autocomplete': 'email'
        })
    )
    
    guardian_phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': _('08012345678'),
            'class': 'form-control guardian-field',
            'autocomplete': 'tel'
        })
    )
    
    guardian_surname = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': _('Guardian surname'),
            'class': 'form-control guardian-field',
            'autocomplete': 'family-name'
        })
    )
    
    guardian_firstname = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': _('Guardian first name'),
            'class': 'form-control guardian-field',
            'autocomplete': 'given-name'
        })
    )
    
    guardian_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Guardian address'),
            'class': 'form-control guardian-field',
            'autocomplete': 'street-address'
        })
    )
    
    guardian_relationship = forms.ChoiceField(
        required=False,
        choices=Guardian._meta.get_field('relationship').choices,
        initial='Parent',
        widget=forms.Select(attrs={'class': 'form-control guardian-field'})
    )
    
    # Existing guardian lookup
    existing_guardian = forms.ModelChoiceField(
        queryset=Guardian.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-placeholder': _('Search for existing guardian...')
        }),
        help_text=_("Or select existing guardian instead of creating new")
    )
    
    # Photo upload
    passport = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        }),
        help_text=_("Passport photo (optional)")
    )
    
    # Quick activation options
    auto_assign_class = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Auto-assign to current session"),
        help_text=_("Assign to current academic session automatically")
    )
    
    class Meta:
        model = Student
        fields = [
            'surname', 'firstname', 'other_name', 'gender', 'date_of_birth',
            'email', 'mobile_number', 'address',
            'current_class', 'current_session',
            'medical_conditions', 'allergies',
            'passport',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current session as default if auto_assign_class is checked
        if self.data.get('auto_assign_class'):
            try:
                current_session = AcademicSession.objects.get(current=True)
                self.fields['current_session'].initial = current_session
            except AcademicSession.DoesNotExist:
                pass
        
        # Order classes by name
        self.fields['current_class'].queryset = StudentClass.objects.all().order_by('name')
        
        # Order sessions by name (most recent first)
        self.fields['current_session'].queryset = AcademicSession.objects.all().order_by('-name')
        
        # Add CSS classes for validation
        for field_name, field in self.fields.items():
            if field_name not in ['include_guardian', 'auto_assign_class']:
                if field.required:
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' required'
    
    def clean_date_of_birth(self):
        """Validate date of birth"""
        dob = self.cleaned_data['date_of_birth']
        
        if dob > timezone.now().date():
            raise ValidationError(_("Date of birth cannot be in the future"))
        
        # Calculate age
        today = timezone.now().date()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        # Age validation for school (3-25 years)
        if age < 3:
            raise ValidationError(_("Student must be at least 3 years old"))
        if age > 25:
            raise ValidationError(_("Student age seems too high. Please verify."))
        
        return dob
    
    def clean_mobile_number(self):
        """Validate Nigerian phone number"""
        phone = self.cleaned_data.get('mobile_number', '').strip()
        
        if not phone:
            return ''
        
        # Clean phone number
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')
        
        # Convert to Nigerian format
        if phone.startswith('234') and len(phone) == 13:
            phone = '0' + phone[3:]
        elif phone.startswith('234') and len(phone) == 12:
            phone = '0' + phone[3:]
        
        # Validate Nigerian number
        if len(phone) != 11:
            raise ValidationError(_("Phone number must be 11 digits"))
        
        if not phone.startswith(('070', '080', '081', '090', '091')):
            raise ValidationError(_("Please enter a valid Nigerian phone number"))
        
        return phone
    
    def clean_guardian_phone(self):
        """Validate guardian phone number"""
        phone = self.cleaned_data.get('guardian_phone', '').strip()
        
        if not phone:
            return ''
        
        # Same validation as mobile_number
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')
        
        if phone.startswith('234') and len(phone) == 13:
            phone = '0' + phone[3:]
        elif phone.startswith('234') and len(phone) == 12:
            phone = '0' + phone[3:]
        
        if len(phone) != 11:
            raise ValidationError(_("Guardian phone must be 11 digits"))
        
        if not phone.startswith(('070', '080', '081', '090', '091')):
            raise ValidationError(_("Please enter a valid Nigerian phone number for guardian"))
        
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        include_guardian = cleaned_data.get('include_guardian')
        existing_guardian = cleaned_data.get('existing_guardian')
        
        # Guardian validation
        if include_guardian and not existing_guardian:
            # Check if new guardian info is provided
            guardian_email = cleaned_data.get('guardian_email')
            guardian_phone = cleaned_data.get('guardian_phone')
            guardian_surname = cleaned_data.get('guardian_surname')
            guardian_firstname = cleaned_data.get('guardian_firstname')
            
            if not guardian_email:
                self.add_error('guardian_email', _("Guardian email is required"))
            
            if not guardian_phone:
                self.add_error('guardian_phone', _("Guardian phone is required"))
            
            if not guardian_surname:
                self.add_error('guardian_surname', _("Guardian surname is required"))
            
            if not guardian_firstname:
                self.add_error('guardian_firstname', _("Guardian first name is required"))
            
            # Check if guardian with this email already exists
            if guardian_email:
                if Guardian.objects.filter(email=guardian_email).exists():
                    self.add_error(
                        'guardian_email',
                        _("A guardian with this email already exists. Please use 'Existing Guardian' field.")
                    )
        
        # If existing guardian is selected, ignore new guardian fields
        if existing_guardian:
            # Clear guardian-related errors if existing guardian is selected
            for field in ['guardian_email', 'guardian_phone', 'guardian_surname', 'guardian_firstname']:
                if field in self.errors:
                    del self.errors[field]
        
        # Auto-assign current session
        if cleaned_data.get('auto_assign_class') and not cleaned_data.get('current_session'):
            try:
                current_session = AcademicSession.objects.get(current=True)
                cleaned_data['current_session'] = current_session
            except AcademicSession.DoesNotExist:
                pass
        
        return cleaned_data

class QuickStudentForm(forms.ModelForm):
    """Quick student creation form for bulk or rapid entry"""
    
    # Multiple students in one form
    students_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': _('''Format: Surname, Firstname, Other Names (optional), Gender, Date of Birth (YYYY-MM-DD), Class
Example:
Adeboye, Chinedu, Michael, Male, 2015-06-15, Primary 5
Aisha, Fatima,, Female, 2016-03-22, Primary 4
Chukwu, Ibrahim, Adamu, Male, 2014-11-30, Primary 6'''),
            'class': 'form-control monospace'
        }),
        help_text=_("Enter one student per line. Separate fields with commas.")
    )
    
    # Common guardian for all students
    common_guardian = forms.ModelChoiceField(
        queryset=Guardian.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=_("Assign same guardian to all students (optional)")
    )
    
    current_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Student
        fields = []  # No direct model fields
    
    def clean_students_data(self):
        """Parse and validate bulk student data"""
        data = self.cleaned_data['students_data']
        lines = [line.strip() for line in data.split('\n') if line.strip()]
        
        parsed_students = []
        errors = []
        
        for i, line in enumerate(lines, 1):
            parts = [part.strip() for part in line.split(',')]
            
            if len(parts) < 5:
                errors.append(f"Line {i}: Insufficient data. Need at least 5 fields.")
                continue
            
            try:
                # Parse fields
                surname = parts[0]
                firstname = parts[1]
                other_name = parts[2] if len(parts) > 2 and parts[2] else ''
                gender = parts[3]
                date_of_birth = parts[4]
                current_class_name = parts[5] if len(parts) > 5 else ''
                
                # Validate gender
                if gender not in ['Male', 'Female']:
                    errors.append(f"Line {i}: Gender must be 'Male' or 'Female'")
                    continue
                
                # Validate date
                from datetime import datetime
                try:
                    dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                    if dob > timezone.now().date():
                        errors.append(f"Line {i}: Date of birth cannot be in the future")
                        continue
                except ValueError:
                    errors.append(f"Line {i}: Invalid date format. Use YYYY-MM-DD")
                    continue
                
                # Get or validate class
                current_class = None
                if current_class_name:
                    try:
                        current_class = StudentClass.objects.get(name=current_class_name)
                    except StudentClass.DoesNotExist:
                        errors.append(f"Line {i}: Class '{current_class_name}' not found")
                        continue
                
                parsed_students.append({
                    'surname': surname,
                    'firstname': firstname,
                    'other_name': other_name,
                    'gender': gender,
                    'date_of_birth': dob,
                    'current_class': current_class,
                    'raw_line': line,
                })
                
            except Exception as e:
                errors.append(f"Line {i}: Error parsing - {str(e)}")
        
        if errors:
            raise ValidationError(errors)
        
        return parsed_students

class StudentActivationForm(forms.Form):
    """Form for activating inactive students"""
    
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.filter(status=Student.Status.INACTIVE),
        widget=forms.CheckboxSelectMultiple,
        label=_("Select Students to Activate")
    )
    
    assign_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        required=False,
        label=_("Assign to Class (optional)"),
        help_text=_("Will assign to selected class if student has no class")
    )
    
    assign_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        required=True,
        label=_("Assign Academic Session"),
        help_text=_("Required for activation")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to show only students that can be activated
        activatable = []
        for student in self.fields['students'].queryset:
            missing = student.get_activation_requirements()
            # Can activate if only missing class and/or session
            if 'Guardian/Parent' not in missing:
                activatable.append(student.pk)
        
        self.fields['students'].queryset = Student.objects.filter(
            pk__in=activatable
        ).select_related('guardian')
        
        # Set default session to current
        try:
            current_session = AcademicSession.objects.get(current=True)
            self.fields['assign_session'].initial = current_session
        except AcademicSession.DoesNotExist:
            pass
    
    def clean(self):
        cleaned_data = super().clean()
        students = cleaned_data.get('students', [])
        assign_class = cleaned_data.get('assign_class')
        assign_session = cleaned_data.get('assign_session')
        
        # Check each student can be activated with provided data
        for student in students:
            missing = student.get_activation_requirements()
            
            if 'Guardian/Parent' in missing:
                self.add_error('students', 
                    _(f"{student} has no guardian and cannot be activated"))
            
            if 'Class' in missing and not assign_class:
                self.add_error('assign_class',
                    _(f"{student} has no class. Please assign a class."))
        
        return cleaned_data


class CreateStudentForm(forms.ModelForm):
    """Form for manual student creation"""
    
    # Guardian fields (optional)
    guardian_email = forms.EmailField(required=False, label=_("Guardian Email"))
    guardian_phone = forms.CharField(required=False, max_length=20, label=_("Guardian Phone"))
    guardian_surname = forms.CharField(required=False, max_length=200, label=_("Guardian Surname"))
    guardian_firstname = forms.CharField(required=False, max_length=200, label=_("Guardian First Name"))
    guardian_address = forms.CharField(required=False, widget=forms.Textarea, label=_("Guardian Address"))
    guardian_relationship = forms.ChoiceField(
        required=False,
        choices=Guardian._meta.get_field('relationship').choices,
        initial='Parent',
        label=_("Relationship")
    )
    
    class Meta:
        model = Student
        fields = [
            'surname', 'firstname', 'other_name', 'gender', 'date_of_birth',
            'email', 'mobile_number', 'address',
            'current_class', 'current_session',
            'medical_conditions', 'allergies',
            'passport',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make class and session optional for manual creation
        self.fields['current_class'].required = False
        self.fields['current_session'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If guardian email is provided, ensure phone is also provided
        if cleaned_data.get('guardian_email') and not cleaned_data.get('guardian_phone'):
            self.add_error('guardian_phone', _("Phone number is required when email is provided"))
        
        return cleaned_data

class BulkCreateStudentsForm(forms.Form):
    """Form for bulk student creation from applications"""
    
    applications = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.CheckboxSelectMultiple,
        label=_("Select Applications"),
        help_text=_("Select approved applications to create students from")
    )
    
    auto_activate = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Auto-activate students"),
        help_text=_("Activate students immediately after creation")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import AdmissionApplication
        self.fields['applications'].queryset = AdmissionApplication.objects.filter(
            status=AdmissionApplication.ApplicationStatus.APPROVED
        ).exclude(
            student__isnull=False
        ).select_related('admission_class', 'admission_session')

class StudentActivationForm(forms.ModelForm):
    """Form for activating a student"""
    
    class Meta:
        model = Student
        fields = ['current_class', 'current_session', 'guardian']
        widgets = {
            'guardian': forms.Select(attrs={'class': 'select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        if instance:
            # Only show missing requirements
            missing = instance.get_activation_requirements()
            if 'Guardian/Parent' not in missing:
                self.fields['guardian'].widget = forms.HiddenInput()
                self.fields['guardian'].required = False
            if 'Class' not in missing:
                self.fields['current_class'].widget = forms.HiddenInput()
                self.fields['current_class'].required = False
            if 'Academic Session' not in missing:
                self.fields['current_session'].widget = forms.HiddenInput()
                self.fields['current_session'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        
        # Check activation requirements
        guardian = cleaned_data.get('guardian', instance.guardian)
        current_class = cleaned_data.get('current_class', instance.current_class)
        current_session = cleaned_data.get('current_session', instance.current_session)
        
        if not guardian or not current_class or not current_session:
            raise forms.ValidationError(
                _("All requirements (guardian, class, session) must be met to activate")
            )
        
        return cleaned_data

class BulkActivationForm(forms.Form):
    """Form for bulk student activation"""
    
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.filter(status=Student.Status.INACTIVE),
        widget=forms.CheckboxSelectMultiple,
        label=_("Select Students"),
        help_text=_("Only students with guardian, class, and session will be activated")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show activatable students
        activatable = []
        for student in self.fields['students'].queryset:
            if student.is_activatable:
                activatable.append(student.pk)
        
        self.fields['students'].queryset = Student.objects.filter(
            pk__in=activatable
        )