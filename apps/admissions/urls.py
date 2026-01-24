from django.urls import path
from . import views

app_name = 'admissions'

urlpatterns = [
    # Public routes
    path('apply/', views.CreateAdmissionApplicationView.as_view(), name='application_create'),
    path('submitted/', views.application_submitted, name='application_submitted'),
    
    # Admin routes
    path('', views.admission_dashboard, name='dashboard'),
    path('applications/', views.AdmissionApplicationListView.as_view(), name='application_list'),
    path('applications/<int:pk>/', views.AdmissionApplicationDetailView.as_view(), name='application_detail'),
    path('applications/<int:pk>/review/', views.ReviewAdmissionApplicationView.as_view(), name='application_review'),
    path('applications/<int:pk>/decision/', views.AdmissionDecisionView.as_view(), name='application_decision'),
    path('applications/<int:pk>/verify-payment/', views.VerifyPaymentView.as_view(), name='verify_payment'),
    path('applications/<int:pk>/send-letter/', views.send_admission_letter_view, name='send_admission_letter'),
    
    # PHASE 2: Payment routes
    path('bulk-verify/', views.bulk_verify_payments, name='bulk_verify_payments'),
    path('api/payment-status/<int:pk>/', views.payment_status_api, name='payment_status_api'),
    
    # PHASE 3: Decision routes
    path('bulk-decision/', views.bulk_decision_view, name='bulk_decision'),
    path('waitlist/', views.waitlist_dashboard, name='waitlist_dashboard'),
    path('waitlist/<int:pk>/manage/', views.WaitlistManagementView.as_view(), name='waitlist_manage'),
    path('waitlist/<int:pk>/promote/', views.promote_from_waitlist, name='promote_from_waitlist'),
    
    # PHASE 4: Student Creation URLs
    path('students/create-from-application/<int:pk>/', views.CreateStudentFromApplicationView.as_view(), name='create_student_from_application'),
    path('students/bulk-create/', views.bulk_create_students_view, name='bulk_create_students'),
    path('students/manual-create/', views.ManualStudentCreationView.as_view(), name='manual_student_create'),
    path('students/<int:pk>/activate/', views.StudentActivationView.as_view(), name='student_activate'),
    path('students/bulk-activate/', views.bulk_activate_students_view, name='bulk_activate_students'),
    path('students/dashboard/', views.student_creation_dashboard, name='student_creation_dashboard'),
    path('students/<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),

    
    # PHASE 6: Enhanced manual student creation
    path('students/enhanced-create/', views.EnhancedManualStudentCreationView.as_view(), name='enhanced_manual_create'),
    path('students/quick-create/', views.QuickStudentCreationView.as_view(), name='quick_student_create'),
    path('students/inactive/', views.InactiveStudentsListView.as_view(), name='inactive_students'),
    path('students/activation-wizard/', views.StudentActivationWizardView.as_view(), name='activation_wizard'),
    path('students/bulk-update/', views.bulk_update_students, name='bulk_update_students'),
]