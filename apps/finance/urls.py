from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    # Invoice URLs
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", views.SafeInvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/bulk/", views.BulkInvoiceCreateView.as_view(), name="bulk_invoice"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/print/", views.invoice_print_view, name="invoice_print"),
    
    # Receipt URLs
    path("receipts/", views.ReceiptListView.as_view(), name="receipt_list"),
    path("receipts/create/", views.ReceiptCreateView.as_view(), name="receipt_create"),
    path("receipts/<int:pk>/", views.ReceiptDetailView.as_view(), name="receipt_detail"),
    
    # Partial Payments
    path("invoices/<int:invoice_id>/partial-payment/", views.add_partial_payment, name="add_partial_payment"),
    
    # Fee Structure URLs
    path("fee-structures/", views.FeeStructureListView.as_view(), name="fee_structure_list"),
    path("fee-structures/create/", views.FeeStructureCreateView.as_view(), name="fee_structure_create"),
    path("fee-structures/<int:pk>/update/", views.FeeStructureUpdateView.as_view(), name="fee_structure_update"),
    path("fee-structures/<int:pk>/delete/", views.FeeStructureDeleteView.as_view(), name="fee_structure_delete"),
    
    # Guardian Financial URLs
    path("guardians/<int:pk>/financial/", views.GuardianFinancialView.as_view(), name="guardian_financial"),
    
    # Reports
    path("reports/", views.FinancialReportView.as_view(), name="financial_report"),
    path("reports/export/", views.export_financial_report, name="export_financial_report"),
    
    # AJAX endpoints
    path("ajax/guardian/<int:guardian_id>/summary/", views.get_guardian_summary_ajax, name="guardian_summary_ajax"),
    path("ajax/student/<int:student_id>/invoice-eligibility/", views.check_student_invoice_eligibility, name="check_invoice_eligibility"),
]