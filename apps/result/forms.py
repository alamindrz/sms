"""
Forms for result management
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from .models import Result, ResultBatch
from apps.students.models import Student
from apps.corecode.models import Subject, AcademicSession, AcademicTerm, StudentClass
from apps.result.utils import validate_student_for_results, get_eligible_students_for_results


class ResultForm(forms.ModelForm):
    """Form for creating/editing individual results"""
    class Meta:
        model = Result
        fields = ['student', 'session', 'term', 'subject', 'test_score', 'exam_score']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'test_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '40',
                'step': '1'
            }),
            'exam_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '60',
                'step': '1'
            }),
        }
        labels = {
            'test_score': _('Test Score (40%)'),
            'exam_score': _('Exam Score (60%)'),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active sessions
        self.fields['session'].queryset = AcademicSession.objects.filter(is_current=True)
        
        # Filter current term if applicable
        self.fields['term'].queryset = AcademicTerm.objects.filter(is_current=True)
        
        # Limit subjects to those offered in student's class
        if self.instance and self.instance.student:
            self.fields['subject'].queryset = Subject.objects.filter(
                classes__id=self.instance.student.current_class.id
            )
        else:
            self.fields['subject'].queryset = Subject.objects.all()
        
        # Add help text
        self.fields['test_score'].help_text = _('Maximum: 40 marks')
        self.fields['exam_score'].help_text = _('Maximum: 60 marks')
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        subject = cleaned_data.get('subject')
        
        if student and session and term and subject:
            # Check if student can receive results
            try:
                validate_student_for_results(student.id, session.id, term.id)
            except ValidationError as e:
                self.add_error('student', str(e))
            
            # Check if student is in a class that offers this subject
            if student.current_class:
                if not subject.classes.filter(id=student.current_class.id).exists():
                    self.add_error('subject', 
                        _('This subject is not offered in %(class)s') % 
                        {'class': student.current_class})
            
            # Check if result already exists
            existing = Result.objects.filter(
                student=student,
                session=session,
                term=term,
                subject=subject
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(None, 
                    _('Result already exists for this student, session, term and subject'))
        
        return cleaned_data


class ResultBatchForm(forms.ModelForm):
    """Form for creating result batches"""
    class Meta:
        model = ResultBatch
        fields = ['name', 'session', 'term', 'student_class']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., JSS1 First Term Results 2024')
            }),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'student_class': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active sessions
        self.fields['session'].queryset = AcademicSession.objects.filter(is_current=True)
        
        # Filter current term
        self.fields['term'].queryset = AcademicTerm.objects.filter(is_current=True)
        
        # Add help text
        self.fields['name'].help_text = _('Give this batch a descriptive name for easy reference')
    
    def clean(self):
        cleaned_data = super().clean()
        session = cleaned_data.get('session')
        term = cleaned_data.get('term')
        student_class = cleaned_data.get('student_class')
        
        if session and term and student_class:
            # Check for existing incomplete batch
            existing = ResultBatch.objects.filter(
                session=session,
                term=term,
                student_class=student_class,
                is_completed=False
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(None, 
                    _('An incomplete result batch already exists for this class, session, and term'))
        
        return cleaned_data


class BulkResultForm(forms.Form):
    """Form for bulk result entry"""
    batch = forms.ModelChoiceField(
        queryset=ResultBatch.objects.filter(is_completed=False),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Result Batch'),
        help_text=_('Select an existing batch or create a new one')
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Subject'),
        help_text=_('Select subject for which to enter results')
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit batches to those created by current user or all for admins
        if self.user and not self.user.is_superuser:
            self.fields['batch'].queryset = ResultBatch.objects.filter(
                is_completed=False,
                created_by__user=self.user
            )
    
    def clean(self):
        cleaned_data = super().clean()
        batch = cleaned_data.get('batch')
        subject = cleaned_data.get('subject')
        
        if batch and subject:
            # Check if subject is offered in this class
            if not subject.classes.filter(id=batch.student_class.id).exists():
                self.add_error('subject', 
                    _('This subject is not offered in %(class)s') % 
                    {'class': batch.student_class})
            
            # Check if results already exist for this batch and subject
            existing_results = Result.objects.filter(
                session=batch.session,
                term=batch.term,
                subject=subject,
                student__current_class=batch.student_class
            ).exists()
            
            if existing_results:
                self.add_error(None, 
                    _('Results already exist for %(subject)s in this batch') % 
                    {'subject': subject})
        
        return cleaned_data


class StudentResultForm(forms.Form):
    """Form for entering results for a specific student in bulk"""
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Student'),
        disabled=True  # Usually set programmatically
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session')
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Term')
    )
    
    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        session = kwargs.pop('session', None)
        term = kwargs.pop('term', None)
        super().__init__(*args, **kwargs)
        
        if student:
            self.fields['student'].initial = student
            self.fields['student'].queryset = Student.objects.filter(pk=student.pk)
            
            # Get subjects offered by student's class
            if student.current_class:
                subjects = Subject.objects.filter(classes__id=student.current_class.id)
                
                # Create a field for each subject
                for subject in subjects:
                    self.fields[f'subject_{subject.id}_test'] = forms.IntegerField(
                        required=False,
                        min_value=0,
                        max_value=40,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'placeholder': _('Test (40)'),
                            'data-subject': subject.id,
                            'data-type': 'test'
                        }),
                        label=f'{subject.name} - Test',
                        help_text=_('0-40 marks')
                    )
                    
                    self.fields[f'subject_{subject.id}_exam'] = forms.IntegerField(
                        required=False,
                        min_value=0,
                        max_value=60,
                        widget=forms.NumberInput(attrs={
                            'class': 'form-control',
                            'placeholder': _('Exam (60)'),
                            'data-subject': subject.id,
                            'data-type': 'exam'
                        }),
                        label=f'{subject.name} - Exam',
                        help_text=_('0-60 marks')
                    )
        
        if session:
            self.fields['session'].initial = session
        
        if term:
            self.fields['term'].initial = term


class ResultFilterForm(forms.Form):
    """Form for filtering results"""
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session'),
        required=False
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Term'),
        required=False
    )
    
    student_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Class'),
        required=False
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Subject'),
        required=False
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Student'),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current session and term as defaults
        current_session = AcademicSession.objects.filter(is_current=True).first()
        current_term = AcademicTerm.objects.filter(is_current=True).first()
        
        if current_session:
            self.fields['session'].initial = current_session
        
        if current_term:
            self.fields['term'].initial = current_term


class ResultUploadForm(forms.Form):
    """Form for uploading results via CSV"""
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session'),
        required=True
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Term'),
        required=True
    )
    
    student_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Class'),
        required=True
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Subject'),
        required=True
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        label=_('CSV File'),
        help_text=_('Upload CSV file with columns: student_number, test_score, exam_score')
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check file extension
        if not csv_file.name.endswith('.csv'):
            raise ValidationError(_('Please upload a CSV file'))
        
        # Check file size (max 5MB)
        if csv_file.size > 5 * 1024 * 1024:
            raise ValidationError(_('File size must be less than 5MB'))
        
        return csv_file


class ResultSummaryForm(forms.Form):
    """Form for generating result summaries/report cards"""
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Student'),
        required=True
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session'),
        required=True
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Term'),
        required=True
    )
    
    include_comments = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('Include teacher comments'),
        help_text=_('Include remarks and comments in the report')
    )
    
    include_position = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('Include class position'),
        help_text=_('Calculate and include student position in class')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current session and term as defaults
        current_session = AcademicSession.objects.filter(is_current=True).first()
        current_term = AcademicTerm.objects.filter(is_current=True).first()
        
        if current_session:
            self.fields['session'].initial = current_session
        
        if current_term:
            self.fields['term'].initial = current_term


class PromotionEligibilityForm(forms.Form):
    """Form for checking promotion eligibility"""
    from_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('From Class'),
        help_text=_('Select the current class of students')
    )
    
    to_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('To Class'),
        help_text=_('Select the class to promote students to')
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session'),
        help_text=_('Select the academic session for promotion')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        from_class = cleaned_data.get('from_class')
        to_class = cleaned_data.get('to_class')
        
        if from_class and to_class:
            # Prevent promoting to the same class
            if from_class == to_class:
                self.add_error('to_class', 
                    _('Promotion must be to a different class'))
            
            # Check if promotion makes sense (e.g., not from higher to lower class)
            # You might want to implement class hierarchy logic here
            
            # Check if target class exists
            if not StudentClass.objects.filter(pk=to_class.id).exists():
                self.add_error('to_class', 
                    _('Target class does not exist'))
        
        return cleaned_data


class ResultCommentForm(forms.Form):
    """Form for adding comments to student results"""
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    teacher_comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Enter teacher\'s comment...')
        }),
        label=_('Teacher\'s Comment'),
        required=False,
        max_length=500
    )
    
    principal_comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Enter principal\'s comment...')
        }),
        label=_('Principal\'s Comment'),
        required=False,
        max_length=500
    )
    
    behavior_rating = forms.ChoiceField(
        choices=[
            ('', '--- Select Rating ---'),
            ('Excellent', 'Excellent'),
            ('Very Good', 'Very Good'),
            ('Good', 'Good'),
            ('Fair', 'Fair'),
            ('Poor', 'Poor'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Behavior Rating'),
        required=False
    )
    
    attendance_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '365'
        }),
        label=_('Days Present'),
        required=False,
        help_text=_('Number of days student was present')
    )
    
    total_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '365'
        }),
        label=_('Total School Days'),
        required=False,
        initial=180,
        help_text=_('Total number of school days in term')
    )