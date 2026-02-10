from django.contrib import admin
from django.utils.html import format_html
from .models import StudentBulkUpload, Guardian

@admin.register(StudentBulkUpload)
class StudentBulkUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_uploaded', 'task_status', 'progress_display', 
                   'records_created', 'records_failed', 'duration_display')
    list_filter = ('task_status', 'date_uploaded')
    readonly_fields = ('task_id', 'task_status', 'processing_started', 'processing_completed',
                      'total_records', 'records_processed', 'records_created', 'records_failed',
                      'progress_percentage', 'current_status_message', 'error_message',
                      'duration_display', 'progress_bar')
    fieldsets = (
        ('Upload Information', {
            'fields': ('csv_file', 'date_uploaded')
        }),
        ('Processing Status', {
            'fields': ('task_status', 'task_id', 'current_status_message', 'progress_bar')
        }),
        ('Statistics', {
            'fields': ('total_records', 'records_processed', 'records_created', 
                      'records_failed', 'progress_percentage')
        }),
        ('Timestamps', {
            'fields': ('processing_started', 'processing_completed', 'duration_display')
        }),
        ('Errors', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def progress_display(self, obj):
        if obj.task_status == 'processing':
            return format_html(
                '<div style="width:100px;background:#ddd;border-radius:3px;">'
                '<div style="width:{}%;background:#4CAF50;height:20px;border-radius:3px;'
                'text-align:center;color:white;font-weight:bold;">{}%</div></div>',
                obj.progress_percentage, obj.progress_percentage
            )
        return obj.get_task_status_display()
    progress_display.short_description = 'Progress'
    
    def duration_display(self, obj):
        if obj.duration:
            return f"{obj.duration:.1f}s"
        return "-"
    duration_display.short_description = 'Duration'
    
    def progress_bar(self, obj):
        return self.progress_display(obj)
    progress_bar.short_description = 'Progress Bar'


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'user_creation_status', 'user_display', 
                   'student_count', 'last_welcome_email')
    list_filter = ('user_creation_status', 'relationship')
    readonly_fields = ('user_creation_task_id', 'user_creation_status', 
                      'user_created_at', 'last_welcome_email_sent')
    
    def user_display(self, obj):
        if obj.user:
            return obj.user.username
        return "No user"
    user_display.short_description = 'User Account'
    
    def last_welcome_email(self, obj):
        if obj.last_welcome_email_sent:
            return obj.last_welcome_email_sent.strftime('%Y-%m-%d %H:%M')
        return "Never"
    last_welcome_email.short_description = 'Welcome Email'