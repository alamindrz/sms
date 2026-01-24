from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import AdmissionApplication, AdmissionReviewLog

@receiver(pre_save, sender=AdmissionApplication)
def log_status_changes(sender, instance, **kwargs):
    """Log status changes automatically"""
    if instance.pk:
        try:
            old_instance = AdmissionApplication.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Create log entry
                AdmissionReviewLog.objects.create(
                    application=instance,
                    staff=instance.reviewed_by or instance.decision_by,
                    action='STATUS_CHANGE',
                    notes=f'Status changed from {old_instance.status} to {instance.status}',
                    from_status=old_instance.status,
                    to_status=instance.status
                )
        except AdmissionApplication.DoesNotExist:
            pass

@receiver(post_save, sender=AdmissionApplication)
def send_status_notifications(sender, instance, created, **kwargs):
    """Send email notifications on status changes"""
    if not created and instance.pk:
        try:
            old_instance = AdmissionApplication.objects.get(pk=instance.pk)
            
            # Check if status changed
            if old_instance.status != instance.status:
                subject = None
                message = None
                
                if instance.status == AdmissionApplication.ApplicationStatus.APPROVED:
                    subject = f"Admission Approved - {instance.application_number}"
                    message = f"""
                    Dear {instance.guardian_name},
                    
                    We are pleased to inform you that the admission application for 
                    {instance.full_name} has been APPROVED for {instance.admission_class} 
                    for the {instance.admission_session} academic session.
                    
                    Application Number: {instance.application_number}
                    
                    Next steps:
                    1. You will receive a formal admission letter shortly
                    2. Complete the acceptance process
                    3. Pay the required fees
                    
                    Congratulations!
                    {settings.SCHOOL_NAME}
                    """
                
                elif instance.status == AdmissionApplication.ApplicationStatus.REJECTED:
                    subject = f"Admission Update - {instance.application_number}"
                    message = f"""
                    Dear {instance.guardian_name},
                    
                    We regret to inform you that the admission application for 
                    {instance.full_name} has not been successful for the 
                    {instance.admission_session} academic session.
                    
                    Reason: {instance.get_rejection_reason_display()}
                    
                    Thank you for your interest in {settings.SCHOOL_NAME}.
                    
                    Sincerely,
                    {settings.SCHOOL_NAME}
                    """
                
                elif instance.status == AdmissionApplication.ApplicationStatus.WAITLISTED:
                    subject = f"Application Waitlisted - {instance.application_number}"
                    message = f"""
                    Dear {instance.guardian_name},
                    
                    The admission application for {instance.full_name} has been 
                    placed on the waitlist for {instance.admission_class}.
                    
                    Waitlist Position: {instance.waitlist_position}
                    
                    We will contact you if a seat becomes available.
                    
                    {settings.SCHOOL_NAME}
                    """
                
                if subject and message:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.guardian_email],
                        fail_silently=True,
                    )
                    
        except AdmissionApplication.DoesNotExist:
            pass