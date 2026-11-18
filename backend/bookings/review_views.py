"""Staff review queue endpoints (manager/admin only)."""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from core.lang import request_lang
from core.permissions import role_required

from .models import Booking
from .review import fix_review_booking, merge_review_bookings, reject_review_booking
from .serializers import BookingSerializer, PaymentSerializer


class ReviewPagination(PageNumberPagination):
    page_size = 100
    max_page_size = 100


class ReviewBookingSerializer(BookingSerializer):
    departure_id = serializers.IntegerField(read_only=True)
    customer_name = serializers.CharField(source="user.full_name", read_only=True)
    customer_email = serializers.EmailField(source="user.email", read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["departure_id", "customer_name", "customer_email", "payments"]


class ReviewBookingsView(generics.ListAPIView):
    permission_classes = [role_required("manager", "admin")]
    serializer_class = ReviewBookingSerializer
    pagination_class = ReviewPagination

    def get_queryset(self):
        return (Booking.objects.filter(status=Booking.NEEDS_REVIEW)
                .select_related("user", "departure__guide__user", "departure__package")
                .prefetch_related("departure__package__translations", "payments")
                .order_by("created_at", "id"))

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}


class MergeReviewSerializer(serializers.Serializer):
    target_booking_id = serializers.IntegerField(min_value=1)


def _booking_response(booking, request):
    booking = (Booking.objects.select_related("user", "departure__guide__user", "departure__package")
               .prefetch_related("departure__package__translations", "payments").get(pk=booking.pk))
    return ReviewBookingSerializer(booking, context={"lang": request_lang(request)}).data


class FixReviewBookingView(APIView):
    permission_classes = [role_required("manager", "admin")]

    @extend_schema(responses=ReviewBookingSerializer)
    def post(self, request, pk):
        return Response(_booking_response(fix_review_booking(request.user, pk), request))


class RejectReviewBookingView(APIView):
    permission_classes = [role_required("manager", "admin")]

    @extend_schema(responses=ReviewBookingSerializer)
    def post(self, request, pk):
        return Response(_booking_response(reject_review_booking(request.user, pk), request))


class MergeReviewBookingView(APIView):
    permission_classes = [role_required("manager", "admin")]

    @extend_schema(request=MergeReviewSerializer, responses=ReviewBookingSerializer)
    def post(self, request, pk):
        serializer = MergeReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = merge_review_bookings(request.user, pk, serializer.validated_data["target_booking_id"])
        return Response(_booking_response(booking, request))