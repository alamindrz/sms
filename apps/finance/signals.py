from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import Invoice, Receipt, GuardianPaymentSummary
from apps.students.models import Guardian

@receiver(post_save, sender=Invoice)
def update_invoice_guardian(sender, instance, created, **kwargs):
    """Update guardian payment summary when invoice changes"""
    if instance.guardian:
        # Update or create guardian summary
        summary, _ = GuardianPaymentSummary.objects.get_or_create(
            guardian=instance.guardian
        )
        summary.update_summary()

@receiver(post_delete, sender=Invoice)
def update_guardian_on_invoice_delete(sender, instance, **kwargs):
    """Update guardian summary when invoice is deleted"""
    if instance.guardian:
        try:
            summary = GuardianPaymentSummary.objects.get(guardian=instance.guardian)
            summary.update_summary()
        except GuardianPaymentSummary.DoesNotExist:
            pass

@receiver(post_save, sender=Receipt)
def update_invoice_on_receipt(sender, instance, created, **kwargs):
    """Update invoice when receipt is created/updated"""
    if created:
        instance.invoice.amount_paid += instance.amount_paid
        instance.invoice.save()

@receiver(post_save, sender=Guardian)
def create_guardian_payment_summary(sender, instance, created, **kwargs):
    """Create payment summary for new guardian"""
    if created:
        GuardianPaymentSummary.objects.create(guardian=instance)