from django.urls import path
from . import views
from . import views_promotion
from apps.admissions import views as adm_views

app_name = "students"

urlpatterns = [
    # Student Management URLs
    path("list/", views.StudentListView.as_view(), name="student_list"),
    path("create/", views.StudentCreateView.as_view(), name="student_create"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
    path("<int:pk>/update/", views.StudentUpdateView.as_view(), name="student_update"),
    path("delete/<int:pk>/", views.StudentDeleteView.as_view(), name="student_delete"),
    path("upload/", views.StudentBulkUploadView.as_view(), name="student_upload"),
    path("download-csv/", views.DownloadCSVViewdownloadcsv.as_view(), name="download-csv"),
    
    # Guardian URLs
    path("guardians/", views.GuardianListView.as_view(), name="guardian_list"),
    path("guardians/create/", views.GuardianCreateView.as_view(), name="guardian_create"),
    path("guardians/<int:pk>/", views.GuardianDetailView.as_view(), name="guardian_detail"),
    path("guardians/<int:pk>/update/", views.GuardianUpdateView.as_view(), name="guardian_update"),
    path("guardians/<int:pk>/delete/", views.GuardianDeleteView.as_view(), name="guardian_delete"),
    
    # Phase 6: Manual Student Creation URLs
    path("enhanced-create/", adm_views.EnhancedManualStudentCreationView.as_view(), name="enhanced_create"),
    path("quick-create/", adm_views.QuickStudentCreationView.as_view(), name="quick_create"),
    path("inactive/", adm_views.InactiveStudentsListView.as_view(), name="inactive_students"),
    path("bulk-update/", adm_views.bulk_update_students, name="bulk_update_students"),
    path("<int:pk>/activate/", adm_views.StudentActivationView.as_view(), name="student_activate"),
    path("bulk-activate/", adm_views.bulk_activate_students_view, name="bulk_activate_students"),
    
    # Phase 8: Promotion Safety URLs
    path("promotion/safety/", views_promotion.PromotionSafetyView.as_view(), name="promotion_safety"),
    path("promotion/confirm/", views_promotion.promotion_confirmation, name="promotion_confirm"),
    path("promotion/logs/", views_promotion.PromotionLogView.as_view(), name="promotion_logs"),
    path("ajax/check-promotion/", views_promotion.check_promotion_eligibility_ajax, name="check_promotion_eligibility"),
    
    # API URLs
    path("api/activation-status/<int:pk>/", views.student_activation_status_api, name="activation_status_api"),
]