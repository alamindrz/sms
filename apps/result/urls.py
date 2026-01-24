from django.urls import path
from . import views

app_name = 'result'

urlpatterns = [
    # Existing URLs
    path('', views.index, name='index'),
    path('create/', views.create_result, name='create_result'),
    path('edit/<int:pk>/', views.edit_results, name='edit_results'),
    
    # Phase 8: Safety URLs
    path('safe/create/', views.SafeResultCreateView.as_view(), name='safe_create_result'),
    path('batch/create/', views.ResultBatchCreateView.as_view(), name='batch_create'),
    path('batch/<int:batch_id>/bulk/', views.create_bulk_results, name='batch_bulk'),
    path('validation/', views.ResultValidationView.as_view(), name='validation'),
    path('export/eligible/', views.export_eligible_students, name='export_eligible'),
    
    # AJAX endpoints
    path('ajax/check-eligibility/', views.check_student_eligibility, name='check_eligibility'),
    path('ajax/check-bulk-eligibility/', views.check_bulk_eligibility, name='check_bulk_eligibility'),
]