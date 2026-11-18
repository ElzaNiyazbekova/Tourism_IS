from django.urls import path

from .analytics import PackageReportView
from .review_views import FixReviewBookingView, MergeReviewBookingView, RejectReviewBookingView, ReviewBookingsView
from .views import BookingCreateView, BookingDetailView, MyBookingsView, PayBookingView

urlpatterns = [
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
