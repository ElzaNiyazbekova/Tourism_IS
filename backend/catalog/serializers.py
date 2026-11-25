"""Public catalogue serializers.   Owner: Aitore (Application & Development)"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Guide
from core.lang import pick_translation

from .models import Departure, Destination, Review, TourPackage, TourPhoto


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
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "author", "mine", "created_at"]

    def get_author(self, obj):
        return obj.user.full_name.split(" ")[0]    # first name only

    def get_mine(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.user_id == request.user.pk)


class ReviewCreateSerializer(serializers.Serializer):
    package = serializers.IntegerField(min_value=1, required=False)
    package_id = serializers.IntegerField(min_value=1, required=False)
    tour = serializers.IntegerField(min_value=1, required=False)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        ids = [attrs.get(name) for name in ("package", "package_id", "tour") if attrs.get(name) is not None]
        if not ids:
            raise serializers.ValidationError({"package": ["This field is required."]})
        if len(set(ids)) > 1:
            raise serializers.ValidationError({"package": ["Package identifiers do not match."]})
        attrs["package"] = ids[0]
        return attrs


class PublicPhotoSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = TourPhoto
        fields = ["id", "url", "caption", "credit"]


class TourListSerializer(serializers.ModelSerializer):
    """Card in the catalogue. Needs annotations next_departure_at / avg_rating / review_count / cover_photo_id from the view."""
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    destination = DestinationSerializer(read_only=True)
    next_departure_at = serializers.DateTimeField(read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    cover_photo = serializers.SerializerMethodField()

    class Meta:
        model = TourPackage
        fields = ["id", "title", "description", "destination", "base_price", "duration_days",
                  "accommodation_included", "transport_included", "next_departure_at", "avg_rating", "review_count",
                  "cover_photo"]

    def get_cover_photo(self, obj) -> str | None:
        pid = getattr(obj, "cover_photo_id", None)
        return f"/api/photos/{pid}" if pid else None

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
    photos = serializers.SerializerMethodField()

    class Meta(TourListSerializer.Meta):
        fields = TourListSerializer.Meta.fields + ["departures", "reviews", "photos"]

    @extend_schema_field(PublicPhotoSerializer(many=True))
    def get_photos(self, obj):
        return PublicPhotoSerializer(obj.ordered_photos, many=True).data   # set by the view via Prefetch(to_attr=...)

    def get_departures(self, obj):
        """Future departures with the guide and seats left (FR-02)."""
        deps = [d for d in obj.upcoming_departures]          # set by the view via Prefetch(to_attr=...)
        return DepartureSerializer(deps, many=True).data

    def get_reviews(self, obj):
        return ReviewSerializer(
            obj.recent_reviews,
            many=True,
            context=self.context,
        ).data   # set by the view via Prefetch(to_attr=...)


class GuideDepartureSerializer(serializers.ModelSerializer):
    """One upcoming departure on the guide's profile, with the tour it belongs to."""
    package_id = serializers.IntegerField(read_only=True)
    package_title = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()

    class Meta:
        model = Departure
        fields = ["id", "package_id", "package_title", "start_at", "end_at", "seats_total", "seats_available", "is_full"]

    def get_package_title(self, obj):
        t = pick_translation(obj.package.translations.all(), self.context.get("lang", "en"))
        return t.title if t else f"#{obj.package_id}"

    def get_is_full(self, obj):
        return obj.seats_available <= 0


class GuideProfileSerializer(GuideBriefSerializer):
    """Public guide profile (Phase 3). Needs annotation completed_count + attr upcoming_departures from the view."""
    completed_count = serializers.IntegerField(read_only=True)
    member_since = serializers.DateTimeField(source="user.created_at", read_only=True)
    upcoming_departures = serializers.SerializerMethodField()

    class Meta(GuideBriefSerializer.Meta):
        fields = GuideBriefSerializer.Meta.fields + ["member_since", "completed_count", "upcoming_departures"]

    def get_upcoming_departures(self, obj):
        return GuideDepartureSerializer(obj.upcoming_departures, many=True, context=self.context).data
