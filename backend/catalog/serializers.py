"""Public catalogue serializers.   Owner: Aitore (Application & Development)"""
from rest_framework import serializers

from accounts.models import Guide
from core.lang import pick_translation

from .models import Departure, Destination, Review, TourPackage


class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ["id", "name", "country"]


class GuideBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")   # NEVER expose email/phone publicly
    languages = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Guide
        fields = ["id", "full_name", "bio", "languages"]


class DepartureSerializer(serializers.ModelSerializer):
    guide = GuideBriefSerializer(read_only=True)
    is_full = serializers.SerializerMethodField()

    class Meta:
        model = Departure
        fields = ["id", "start_at", "end_at", "seats_total", "seats_available", "is_full", "guide"]

    def get_is_full(self, obj):
        return obj.seats_available <= 0


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "author", "created_at"]

    def get_author(self, obj):
        return obj.user.full_name.split(" ")[0]    # first name only


class TourListSerializer(serializers.ModelSerializer):
    """Card in the catalogue. Needs annotations next_departure_at / avg_rating / review_count from the view."""
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    destination = DestinationSerializer(read_only=True)
    next_departure_at = serializers.DateTimeField(read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TourPackage
        fields = ["id", "title", "description", "destination", "base_price", "duration_days",
                  "accommodation_included", "transport_included", "next_departure_at", "avg_rating", "review_count"]

    def _tr(self, obj):
        return pick_translation(obj.translations.all(), self.context.get("lang", "en"))

    def get_title(self, obj):
        t = self._tr(obj)
        return t.title if t else f"#{obj.pk}"

    def get_description(self, obj):
        t = self._tr(obj)
        return t.description if t else ""


class TourDetailSerializer(TourListSerializer):
    departures = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta(TourListSerializer.Meta):
        fields = TourListSerializer.Meta.fields + ["departures", "reviews"]

    def get_departures(self, obj):
        """Future departures with the guide and seats left (FR-02)."""
        deps = [d for d in obj.upcoming_departures]          # set by the view via Prefetch(to_attr=...)
        return DepartureSerializer(deps, many=True).data

    def get_reviews(self, obj):
        return ReviewSerializer(obj.recent_reviews, many=True).data   # set by the view via Prefetch(to_attr=...)
