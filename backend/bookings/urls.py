from django.urls import path

from .analytics import PackageReportView, AnalystExportView
from .admin_views import AdminBookingsView, AdminReportExportView, AdminStatsView
from .review_views import FixReviewBookingView, MergeReviewBookingView, RejectReviewBookingView, ReviewBookingsView
from .views import BookingCreateView, BookingDetailView, MyBookingsView, PayBookingView

urlpatterns = [
    path("admin/bookings", AdminBookingsView.as_view()),
    path("admin/stats", AdminStatsView.as_view()),
    path("admin/report/export", AdminReportExportView.as_view()),
    path("analytics/export", AnalystExportView.as_view()),
    path("admin/bookings/review", ReviewBookingsView.as_view()),
    path("admin/bookings/<int:pk>/fix", FixReviewBookingView.as_view()),
    path("admin/bookings/<int:pk>/merge", MergeReviewBookingView.as_view()),
    path("admin/bookings/<int:pk>/reject", RejectReviewBookingView.as_view()),
    path("bookings", BookingCreateView.as_view()),
    path("bookings/mine", MyBookingsView.as_view()),
    path("bookings/<int:pk>", BookingDetailView.as_view()),
    path("bookings/<int:pk>/pay", PayBookingView.as_view()),
    path("analytics/packages", PackageReportView.as_view()),
]
