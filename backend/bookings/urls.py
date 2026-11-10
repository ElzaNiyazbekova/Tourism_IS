from django.urls import path

from .analytics import PackageReportView
from .views import BookingCreateView, BookingDetailView, CheckoutView, MyBookingsView, PayBookingView

urlpatterns = [
    path("bookings", BookingCreateView.as_view()),
    path("bookings/mine", MyBookingsView.as_view()),
    path("bookings/checkout", CheckoutView.as_view()),
    path("bookings/<int:pk>", BookingDetailView.as_view()),
    path("bookings/<int:pk>/pay", PayBookingView.as_view()),
    path("analytics/packages", PackageReportView.as_view()),
]
