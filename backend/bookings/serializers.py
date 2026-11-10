"""Owner: Aitore (Application & Development)"""
from rest_framework import serializers

from core.lang import pick_translation

from .models import Booking, Payment


class BookingCreateSerializer(serializers.Serializer):
    """The ONLY things a tourist may send: which departure, how many people, a free-text request."""
    departure = serializers.IntegerField(min_value=1)
    travelers_count = serializers.IntegerField(min_value=1, max_value=50)
    special_request = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class BookingSerializer(serializers.ModelSerializer):
    package_id = serializers.IntegerField(source="departure.package_id", read_only=True)
    package_title = serializers.SerializerMethodField()
    start_at = serializers.DateTimeField(source="departure.start_at", read_only=True)
    guide_name = serializers.CharField(source="departure.guide.user.full_name", read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "booking_ref", "package_id", "package_title", "start_at", "guide_name", "booking_date",
                  "travel_date", "travelers_count", "total_cost", "status", "special_request", "expires_at", "created_at"]

    def get_package_title(self, obj):
        t = pick_translation(obj.departure.package.translations.all(), self.context.get("lang", "en"))
        return t.title if t else f"#{obj.departure.package_id}"


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "amount", "status", "transaction_ref", "paid_at"]


class PaySerializer(serializers.Serializer):
    """Body of POST /api/bookings/{id}/pay - the button pressed on the mock gateway screen."""
    result = serializers.ChoiceField(choices=["pay", "fail"])


class BookingDetailSerializer(BookingSerializer):
    """One booking + its payment attempts (used by the payment screen)."""
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["payments"]
