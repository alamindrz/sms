from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import PasswordChangeForm

class ParentProfileForm(forms.ModelForm):
    """Form for parents to update their profile"""
    
    class Meta:
        from apps.students.models import Guardian
        model = Guardian
        fields = [
            'title', 'surname', 'firstname', 'other_name',
            'email', 'phone', 'phone2', 'address', 'occupation',
            'photo'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Email should be read-only as it's used for login
        self.fields['email'].widget.attrs['readonly'] = True

class ParentPasswordChangeForm(PasswordChangeForm):
    """Custom password change form for parents"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class ContactSchoolForm(forms.Form):
    """Form for parents to contact school"""
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': _('Subject')})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': _('Type your message here...')
        })
    )
    urgency = forms.ChoiceField(
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('urgent', _('Urgent')),
        ],
        initial='medium'
    )
    
    def send_email(self, guardian, student=None):
        """Send the contact message"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = f"Parent Contact: {self.cleaned_data['subject']}"
        
        message = f"""
        From: {guardian.full_name} ({guardian.email})
        Student: {student.full_name if student else 'Not specified'}
        Urgency: {self.cleaned_data['urgency']}
        
        Message:
        {self.cleaned_data['message']}
        
        ---
        This message was sent from the Parent Portal.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
            fail_silently=True,
        )