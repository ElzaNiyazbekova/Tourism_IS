"""
Tourist booking endpoints.   Owner: Aitore (Application & Development)

POST /api/bookings        create a Pending booking (tourist only)
GET  /api/bookings/mine   my bookings, newest first (tourist only)
"""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.lang import request_lang
from core.permissions import role_required

from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer
from .services import create_booking


class BookingCreateView(APIView):
    permission_classes = [role_required("tourist")]

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
    permission_classes = [role_required("tourist")]
    serializer_class = BookingSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    def get_queryset(self):
        return (Booking.objects.filter(user=self.request.user)
                .select_related("departure__guide__user", "departure__package")
                .prefetch_related("departure__package__translations")
                .order_by("-created_at", "-id"))
