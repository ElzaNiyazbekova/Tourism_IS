"""
Guide cabinet: what a logged-in GUIDE sees about their own work.   Owner: Aitore (Application & Development)

GET   /api/guide/me                       own profile + stats
PATCH /api/guide/me  {bio, languages}     edit own bio / spoken languages (audited)
GET   /api/guide/departures?when=upcoming|past&lang=
GET   /api/guide/departures/<id>?lang=    one own departure + its travellers (name, phone, group size, request)

Only role "guide" (403 for everybody else). A guide sees ONLY their own departures (others -> 404).
"""
from django.db import transaction
from django.db.models import Count, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Guide
from bookings.audit import audit
from bookings.models import Booking
from core.exceptions import ApiError
from core.lang import pick_translation, request_lang
from core.permissions import role_required

from .models import Departure

LANG_CODES = ("en", "ru", "kk")
SEAT_HOLDING = [Booking.PENDING, Booking.CONFIRMED, Booking.COMPLETED]   # Cancelled and Expired release seats


def own_guide(user):
    guide = Guide.objects.select_related("user").filter(user=user).first()
    if guide is None:   # role "guide" but no guides row (should not happen with seed / admin data)
        raise ApiError("not_found", "errors.not_found", "No guide profile for this account.", 404)
    return guide


# ---------- serializers ----------

class GuideMeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    languages = serializers.ListField(child=serializers.ChoiceField(choices=LANG_CODES), min_length=1, max_length=3)
    bio = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    upcoming_count = serializers.IntegerField(read_only=True)
    completed_count = serializers.IntegerField(read_only=True)
    travelers_upcoming = serializers.IntegerField(read_only=True)

    class Meta:
        model = Guide
        fields = ["id", "full_name", "email", "bio", "languages", "is_active",
                  "upcoming_count", "completed_count", "travelers_upcoming"]
        read_only_fields = ["id", "is_active"]

    def update(self, guide, data):
        if "languages" in data:
            # keep a stable order (kk, ru, en) and no duplicates
            guide.languages_spoken = ",".join(c for c in ("kk", "ru", "en") if c in data["languages"])
        if "bio" in data:
            guide.bio = data["bio"].strip()
        guide.save(update_fields=["languages_spoken", "bio"])
        return guide


class CabinetDepartureSerializer(serializers.ModelSerializer):
    package_id = serializers.IntegerField(read_only=True)
    package_title = serializers.SerializerMethodField()
    destination = serializers.CharField(source="package.destination.name", read_only=True)
    bookings_count = serializers.IntegerField(read_only=True)
    travelers_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Departure
        fields = ["id", "package_id", "package_title", "destination", "start_at", "end_at",
                  "seats_total", "seats_available", "is_active", "bookings_count", "travelers_count"]

    def get_package_title(self, obj):
        t = pick_translation(obj.package.translations.all(), self.context.get("lang", "en"))
        return t.title if t else f"#{obj.package_id}"


class TravelerSerializer(serializers.ModelSerializer):
    """What a guide needs to run the tour: who comes, how many, how to reach them. No payments / costs."""
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = Booking
        fields = ["booking_ref", "full_name", "phone", "travelers_count", "status", "special_request"]


class CabinetDepartureDetailSerializer(CabinetDepartureSerializer):
    travelers = serializers.SerializerMethodField()

    class Meta(CabinetDepartureSerializer.Meta):
        fields = CabinetDepartureSerializer.Meta.fields + ["travelers"]

    def get_travelers(self, obj):
        rows = obj.bookings.filter(status__in=SEAT_HOLDING).select_related("user").order_by("created_at")
        return TravelerSerializer(rows, many=True).data


# ---------- views ----------

def departures_of(guide):
    held = Q(bookings__status__in=SEAT_HOLDING)
    return (Departure.objects.filter(guide=guide)
            .select_related("package__destination").prefetch_related("package__translations")
            .annotate(bookings_count=Count("bookings", filter=held),
                      travelers_count=Coalesce(Sum("bookings__travelers_count", filter=held), Value(0),
                                               output_field=IntegerField())))


class GuideMeView(APIView):
    permission_classes = [role_required("guide")]

    def _data(self, guide):
        now = timezone.now()
        future = Q(is_active=True, start_at__gt=now)
        stats = Departure.objects.filter(guide=guide).aggregate(
            upcoming_count=Count("pk", filter=future),
            completed_count=Count("pk", filter=Q(is_active=True, end_at__lte=now)))
        stats["travelers_upcoming"] = (Booking.objects.filter(departure__guide=guide, departure__is_active=True,
                                                              departure__start_at__gt=now, status__in=Booking.ACTIVE)
                                       .aggregate(s=Sum("travelers_count"))["s"] or 0)
        for k, v in stats.items():
            setattr(guide, k, v)
        return GuideMeSerializer(guide).data

    @extend_schema(responses=GuideMeSerializer)
    def get(self, request):
        return Response(self._data(own_guide(request.user)))

    @extend_schema(request=GuideMeSerializer, responses=GuideMeSerializer)
    def patch(self, request):
        guide = own_guide(request.user)
        old = {"bio": guide.bio, "languages_spoken": guide.languages_spoken}
        ser = GuideMeSerializer(guide, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            ser.save()
            audit(request.user, "update", "guides", guide.pk, old,
                  {"bio": guide.bio, "languages_spoken": guide.languages_spoken})
        return Response(self._data(guide))


class GuideDepartureListView(generics.ListAPIView):
    permission_classes = [role_required("guide")]
    serializer_class = CabinetDepartureSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    @extend_schema(parameters=[OpenApiParameter("when", str, description="upcoming (default) | past"),
                               OpenApiParameter("lang", str, description="en|ru|kk")])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        when = self.request.query_params.get("when", "upcoming")
        if when not in ("upcoming", "past"):
            raise ApiError("validation_error", "errors.validation", "Invalid value for when.", 400,
                           field_errors={"when": [{"message_key": "errors.field.invalid", "message": "Invalid value."}]})
        qs, now = departures_of(own_guide(self.request.user)), timezone.now()
        if when == "past":
            return qs.filter(start_at__lte=now).order_by("-start_at")
        return qs.filter(start_at__gt=now).order_by("start_at")      # inactive ones stay visible (shown as cancelled)


class GuideDepartureDetailView(generics.RetrieveAPIView):
    permission_classes = [role_required("guide")]
    serializer_class = CabinetDepartureDetailSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    def get_queryset(self):
        return departures_of(own_guide(self.request.user))   # someone else's departure -> 404
