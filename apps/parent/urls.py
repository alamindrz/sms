from django.urls import path
from . import views

app_name = 'parent'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.ParentDashboardView.as_view(), name='dashboard'),
    
    # Wards/Students
    path('my-wards/', views.MyWardsView.as_view(), name='my_wards'),
    path('ward/<int:pk>/', views.WardDetailView.as_view(), name='ward_detail'),
    
    # Academic
    path('results/', views.ResultsView.as_view(), name='results'),
    path('attendance/', views.AttendanceView.as_view(), name='attendance'),
    
    # Finance
    path('payments/', views.PaymentsView.as_view(), name='payments'),
    
    # Communications
    path('announcements/', views.AnnouncementsView.as_view(), name='announcements'),
    path('contact-school/', views.ContactSchoolView.as_view(), name='contact'),
    
    # Profile & Settings
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    
    # API Endpoints
    path('api/notification/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/ward/<int:student_id>/summary/', views.get_ward_summary, name='get_ward_summary'),
]