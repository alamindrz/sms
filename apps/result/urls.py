from django.urls import path
from . import views

app_name = "result"

urlpatterns = [
    # Result Entry URLs
    path("create/", views.SafeResultCreateView.as_view(), name="result_create"),
    
    # Result Batch URLs
    path("batch/create/", views.ResultBatchCreateView.as_view(), name="batch_create"),
    path("batch/<int:batch_id>/bulk/", views.create_bulk_results, name="create_bulk_results"),
    
    # Result Validation URLs
    path("validation/", views.ResultValidationView.as_view(), name="result_validation"),
    path("validation/export/", views.export_eligible_students, name="export_eligible_students"),
    
    # AJAX API Endpoints
    path("ajax/check-eligibility/", views.check_student_eligibility, name="check_eligibility"),
    path("ajax/check-bulk-eligibility/", views.check_bulk_eligibility, name="check_bulk_eligibility"),

    path("list/", views.ResultListView.as_view(), name="result_list"),
    path("<int:pk>/", views.ResultDetailView.as_view(), name="result_detail"),
    path("<int:pk>/update/", views.ResultUpdateView.as_view(), name="result_update"),
    path("<int:pk>/delete/", views.delete_result, name="result_delete"),
    
    
    path("batch/list/", views.ResultBatchListView.as_view(), name="batch_list"),
    path("batch/<int:pk>/", views.ResultBatchDetailView.as_view(), name="batch_detail"),
    path("batch/<int:pk>/complete/", views.complete_batch, name="complete_batch"),
    
]