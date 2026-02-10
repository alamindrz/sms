# admissions/templatetags/admission_filters.py
from django import template

register = template.Library()

@register.filter
def filter_status(queryset, status):
    """Filter applications by status"""
    if not queryset:
        return []
    return [app for app in queryset if app.status == status]

@register.filter
def filter_payment_status(queryset, status):
    """Filter applications by payment status"""
    if not queryset:
        return []
    
    if status == 'verified':
        return [app for app in queryset if app.payment_verified]
    elif status == 'unverified':
        return [app for app in queryset if app.payment_reference and not app.payment_verified]
    elif status == 'unpaid':
        return [app for app in queryset if not app.payment_reference]
    return []

@register.filter
def get_status_class(status):
    """Get CSS class for status badge"""
    status_classes = {
        'pending': 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300',
        'under_review': 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300',
        'approved': 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
        'rejected': 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
        'waitlisted': 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300',
        'accepted': 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300',
    }
    return status_classes.get(status, 'bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300')

@register.filter
def get_payment_class(payment_verified, payment_reference):
    """Get CSS class for payment status"""
    if payment_reference:
        if payment_verified:
            return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
        else:
            return 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300'
    return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'