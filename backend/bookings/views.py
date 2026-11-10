"""
Tourist booking endpoints.   Owner: Aitore (Application & Development)

POST /api/bookings            create a Pending booking (tourist only)
GET  /api/bookings/mine       my bookings, newest first (tourist only)
GET  /api/bookings/{id}       one of my bookings with its payment attempts (payment screen)
POST /api/bookings/{id}/pay   mock gateway: {"result": "pay"|"fail"}
POST /api/bookings/checkout   book + pay in ONE transaction; "fail" rolls everything back (402)
"""
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.lang import request_lang
from core.permissions import IsTourist

from .models import Booking
from .payments import book_and_pay, pay_booking
from .serializers import (BookingCreateSerializer, BookingDetailSerializer, BookingSerializer, CheckoutSerializer,
                          PaymentSerializer, PaySerializer)
from .services import create_booking


class BookingCreateView(APIView):
    permission_classes = [IsTourist]

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def post(self, request):
        ser = BookingCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        booking = create_booking(request.user, ser.validated_data["departure"],
                                 ser.validated_data["travelers_count"], ser.validated_data["special_request"])
        booking = (Booking.objects.select_related("departure__guide__user", "departure__package")
                   .prefetch_related("departure__package__translations").get(pk=booking.pk))
        return Response(BookingSerializer(booking, context={"lang": request_lang(request)}).data,
                        status=status.HTTP_201_CREATED)


class MyBookingsView(generics.ListAPIView):
    permission_classes = [IsTourist]
    serializer_class = BookingSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    def get_queryset(self):
        return (Booking.objects.filter(user=self.request.user)
                .select_related("departure__guide__user", "departure__package")
                .prefetch_related("departure__package__translations")
                .order_by("-created_at", "-id"))


def _booking_qs():
    return (Booking.objects.select_related("departure__guide__user", "departure__package")
            .prefetch_related("departure__package__translations", "payments"))


class BookingDetailView(APIView):
    permission_classes = [IsTourist]

    @extend_schema(responses=BookingDetailSerializer)
    def get(self, request, pk):
        booking = get_object_or_404(_booking_qs(), pk=pk, user=request.user)   # someone else's booking -> 404
        return Response(BookingDetailSerializer(booking, context={"lang": request_lang(request)}).data)


class PayBookingView(APIView):
    """Both outcomes answer 200: look at "result". Business errors (already paid, expired ...) are 409."""
    permission_classes = [IsTourist]

    @extend_schema(request=PaySerializer, responses=BookingDetailSerializer)
    def post(self, request, pk):
        ser = PaySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        booking, payment = pay_booking(request.user, pk, ser.validated_data["result"])
        booking = _booking_qs().get(pk=booking.pk)
        ok = payment.status == "Success"
        return Response({
            "result": payment.status,
            "message_key": "payment.success" if ok else "payment.failed",
            "payment": PaymentSerializer(payment).data,
            "booking": BookingDetailSerializer(booking, context={"lang": request_lang(request)}).data,
        })


class CheckoutView(APIView):
    """
    Book and pay in one step. "pay" -> 201 with the Confirmed booking and its payment.
    "fail" -> 402 payment_failed and NOTHING is saved (booking, payment and seat change are rolled back).
    """
    permission_classes = [IsTourist]

    @extend_schema(request=CheckoutSerializer, responses={201: BookingDetailSerializer})
    def post(self, request):
        ser = CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        booking, payment = book_and_pay(request.user, d["departure"], d["travelers_count"], d["result"], d["special_request"])
        booking = _booking_qs().get(pk=booking.pk)
        return Response({
            "result": payment.status,
            "message_key": "payment.success",
            "payment": PaymentSerializer(payment).data,
            "booking": BookingDetailSerializer(booking, context={"lang": request_lang(request)}).data,
        }, status=status.HTTP_201_CREATED)
