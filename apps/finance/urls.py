from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    # Invoice Management URLs
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", views.SafeInvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/bulk/", views.BulkInvoiceCreateView.as_view(), name="bulk_invoice"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:invoice_id>/partial-payment/", views.add_partial_payment, name="add_partial_payment"),
    
    # Guardian Financial URLs
    path("guardian/<int:pk>/financial/", views.GuardianFinancialView.as_view(), name="guardian_financial"),
    
    # Fee Structure URLs
    path("fee-structures/", views.FeeStructureListView.as_view(), name="fee_structure_list"),
    path("fee-structures/create/", views.FeeStructureCreateView.as_view(), name="fee_structure_create"),
    
    # Financial Reports URLs
    path("reports/", views.FinancialReportView.as_view(), name="financial_report"),
    path("reports/export/", views.export_financial_report, name="export_financial_report"),
    
    # AJAX API Endpoints
    path("ajax/guardian-summary/<int:guardian_id>/", views.get_guardian_summary_ajax, name="guardian_summary_ajax"),
    path("ajax/check-invoice-eligibility/<int:student_id>/", views.check_student_invoice_eligibility, name="check_invoice_eligibility"),
]