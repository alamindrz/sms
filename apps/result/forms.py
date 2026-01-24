from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from .models import Result, ResultBatch
from apps.students.models import Student
from apps.corecode.models import StudentClass, AcademicSession, AcademicTerm, Subject
from .utils import validate_student_for_results, get_eligible_students_for_results

class SafeResultForm(forms.ModelForm):
    """Result form with safety checks"""
    
    class Meta:
        model = Result
        fields = ['student', 'session', 'term', 'subject', 'test_score', 'exam_score']
        widgets = {
            'test_score': forms.NumberInput(attrs={'min': 0, 'max': 40, 'step': 1}),
            'exam_score': forms.NumberInput(attrs={'min': 0, 'max': 60, 'step': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter students to only active ones
        self.fields['student'].queryset = Student.get_active_students().order_by('surname', 'firstname')
        
        # Add help text
        self.fields['student'].help_text = _("Only active students are shown")
        self.fields['test_score'].help_text = _("Maximum: 40")
        self.fields['exam_score'].help_text = _("Maximum: 60")
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        
        if student and session and term:
            try:
                validate_student_for_results(student.id, session.id, term.id)
            except ValidationError as e:
                self.add_error(None, str(e))
        
        return cleaned_data

class ResultBatchForm(forms.ModelForm):
    """Result batch form with validation"""
    
    class Meta:
        model = ResultBatch
        fields = ['name', 'session', 'term', 'student_class']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order choices
        self.fields['session'].queryset = AcademicSession.objects.all().order_by('-name')
        self.fields['term'].queryset = AcademicTerm.objects.all().order_by('name')
        self.fields['student_class'].queryset = StudentClass.objects.all().order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        student_class = cleaned_data.get('student_class')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        
        if student_class and session and term:
            # Check if there are eligible students
            eligible_students = get_eligible_students_for_results(
                class_id=student_class.id,
                session_id=session.id,
                term_id=term.id
            )
            
            if not eligible_students.exists():
                raise ValidationError(
                    _("No active students found in the selected class, session, and term")
                )
        
        return cleaned_data

class BulkResultForm(forms.Form):
    """Form for bulk result entry"""
    
    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)
        
        if self.batch:
            # Get subjects for the class
            subjects = Subject.objects.filter(
                studentclass=self.batch.student_class
            ).order_by('name')
            
            self.fields['subjects'] = forms.ModelMultipleChoiceField(
                queryset=subjects,
                widget=forms.CheckboxSelectMultiple,
                label=_("Subjects"),
                required=True
            )
            
            # Default scores
            self.fields['test_score'] = forms.IntegerField(
                min_value=0,
                max_value=40,
                initial=0,
                label=_("Test Score (for all)"),
                help_text=_("Will be applied to all selected subjects")
            )
            
            self.fields['exam_score'] = forms.IntegerField(
                min_value=0,
                max_value=60,
                initial=0,
                label=_("Exam Score (for all)"),
                help_text=_("Will be applied to all selected subjects")
            )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check if batch is still valid
        if self.batch and self.batch.is_completed:
            raise ValidationError(_("This result batch has been completed"))
        
        return cleaned_data

class ResultValidationForm(forms.Form):
    """Form for validating results before entry"""
    
    student_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        required=False,
        label=_("Class")
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        required=False,
        label=_("Academic Session")
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        required=False,
        label=_("Term")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial values
        try:
            current_session = AcademicSession.objects.get(current=True)
            self.fields['session'].initial = current_session
        except AcademicSession.DoesNotExist:
            pass

class PromotionEligibilityForm(forms.Form):
    """Form for checking promotion eligibility"""
    
    from_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        label=_("From Class")
    )
    
    to_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        label=_("To Class")
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        label=_("Academic Session")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order classes
        self.fields['from_class'].queryset = StudentClass.objects.all().order_by('name')
        self.fields['to_class'].queryset = StudentClass.objects.all().order_by('name')
        
        # Set current session
        try:
            current_session = AcademicSession.objects.get(current=True)
            self.fields['session'].initial = current_session
        except AcademicSession.DoesNotExist:
            pass
    
    def clean(self):
        cleaned_data = super().clean()
        from_class = cleaned_data.get('from_class')
        to_class = cleaned_data.get('to_class')
        
        if from_class and to_class and from_class == to_class:
            raise ValidationError(_("'From Class' and 'To Class' cannot be the same"))
        
        return cleaned_data