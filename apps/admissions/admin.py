from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import AdmissionApplication

@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'application_number', 'full_name', 'age', 'gender',
        'admission_class', 'status', 'payment_verified_badge',
        'application_date', 'created_at'
    ]
    list_filter = [
        'status', 'payment_verified', 'gender', 
        'admission_class', 'admission_session',
        'payment_channel'
    ]
    search_fields = [
        'application_number', 'first_name', 'surname', 
        'guardian_name', 'guardian_phone', 'guardian_email',
        'payment_reference'
    ]
    readonly_fields = [
        'application_number', 'created_at', 'updated_at',
        'payment_verified_by', 'payment_verified_date',
        'reviewed_by', 'review_date', 'decision_date',
        'student'
    ]
    fieldsets = (
        (_('Application Information'), {
            'fields': ('application_number', 'application_date', 
                      'admission_session', 'admission_class', 'status')
        }),
        (_('Guardian Information'), {
            'fields': ('guardian_name', 'guardian_email', 'guardian_phone',
                      'guardian_address', 'guardian_relationship', 'guardian_photo')
        }),
        (_('Student Information'), {
            'fields': ('first_name', 'middle_name', 'surname', 'gender',
                      'date_of_birth', 'birth_certificate_number', 'religion',
                      'student_photo')
        }),
        (_('Educational Background'), {
            'fields': ('previous_school', 'previous_class', 'last_report_card')
        }),
        (_('Medical Information'), {
            'fields': ('medical_conditions', 'allergies', 'doctor_name', 'doctor_phone')
        }),
        (_('Payment Information'), {
            'fields': ('payment_reference', 'payment_verified', 'payment_amount',
                      'payment_channel', 'payment_receipt',
                      'payment_verified_by', 'payment_verified_date')
        }),
        (_('Review & Decision'), {
            'fields': ('review_notes', 'reviewed_by', 'review_date',
                      'decision_notes', 'decision_date', 'student')
        }),
        (_('System Information'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def payment_verified_badge(self, obj):
        if obj.payment_verified:
            return '✅ Verified'
        elif obj.payment_reference:
            return '⚠️ Pending'
        else:
            return '❌ Unpaid'
    payment_verified_badge.short_description = 'Payment Status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user.staff
        super().save_model(request, obj, form, change)