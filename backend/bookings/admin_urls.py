"""Admin and analyst HTTP routes. Owner: Aitore / Dastan"""
from django.urls import path

from .admin_views import AdminBookingsView, AdminReportExportView, AdminStatsView
from .analytics import AnalystExportView

urlpatterns = [
    path("admin/bookings", AdminBookingsView.as_view()),
    path("admin/stats", AdminStatsView.as_view()),
    path("admin/report/export", AdminReportExportView.as_view()),
    path("analytics/export", AnalystExportView.as_view()),
]
