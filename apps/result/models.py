from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.students.models import Student
from apps.corecode.models import Subject, AcademicSession, AcademicTerm

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    test_score = models.IntegerField(default=0)
    exam_score = models.IntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'session', 'term', 'subject']
        ordering = ['student__surname', 'student__firstname', 'subject__name']
    
    def __str__(self):
        return f"{self.student} - {self.subject} - {self.session}"
    
    def clean(self):
        """Validate result entry"""
        from apps.result.utils import validate_student_for_results
        
        # Validate student can receive results
        try:
            validate_student_for_results(
                self.student.id, 
                self.session.id if self.session else None,
                self.term.id if self.term else None
            )
        except ValidationError as e:
            raise ValidationError({'student': str(e)})
        
        # Validate scores
        if self.test_score < 0 or self.test_score > 40:
            raise ValidationError({'test_score': _('Test score must be between 0 and 40')})
        
        if self.exam_score < 0 or self.exam_score > 60:
            raise ValidationError({'exam_score': _('Exam score must be between 0 and 60')})
    
    @property
    def total_score(self):
        return self.test_score + self.exam_score
    
    @property
    def grade(self):
        """Calculate grade based on total score"""
        total = self.total_score
        if total >= 75:
            return 'A'
        elif total >= 65:
            return 'B'
        elif total >= 55:
            return 'C'
        elif total >= 50:
            return 'D'
        elif total >= 45:
            return 'E'
        else:
            return 'F'
    
    @property
    def remark(self):
        """Get remark based on grade"""
        grades = {
            'A': 'Excellent',
            'B': 'Very Good',
            'C': 'Good',
            'D': 'Pass',
            'E': 'Fair',
            'F': 'Fail',
        }
        return grades.get(self.grade, 'Unknown')

class ResultBatch(models.Model):
    """Batch result entry for tracking and validation"""
    name = models.CharField(max_length=200)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    student_class = models.ForeignKey('corecode.StudentClass', on_delete=models.CASCADE)
    created_by = models.ForeignKey('staffs.Staff', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.student_class} - {self.session}"
    
    def clean(self):
        """Validate result batch"""
        # Check if batch already exists for this class, session, term
        existing = ResultBatch.objects.filter(
            session=self.session,
            term=self.term,
            student_class=self.student_class,
            is_completed=False
        ).exclude(pk=self.pk)
        
        if existing.exists():
            raise ValidationError(
                _('An incomplete result batch already exists for this class, session, and term')
            )
    
    @property
    def eligible_students(self):
        """Get students eligible for this result batch"""
        from apps.result.utils import get_eligible_students_for_results
        return get_eligible_students_for_results(
            class_id=self.student_class.id,
            session_id=self.session.id,
            term_id=self.term.id
        )
    
    @property
    def result_count(self):
        """Count results in this batch"""
        return Result.objects.filter(
            session=self.session,
            term=self.term,
            student__current_class=self.student_class
        ).count()
    
    @property
    def student_count(self):
        """Count students in this batch"""
        return self.eligible_students.count()