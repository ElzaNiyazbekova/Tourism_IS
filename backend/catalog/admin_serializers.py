"""Staff (manager/admin) serializers for tours and departures.   Owner: Aitore (views) / Amina A. (rules)"""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Guide
from bookings.models import Booking
from core.exceptions import ApiError
from core.lang import pick_translation

from .models import Departure, Destination, PackageTranslation, TourPackage
from .services import assert_no_guide_overlap


class AdminDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ["id", "name", "country"]


class AdminGuideSerializer(serializers.ModelSerializer):
    """Guides for the dropdown. Deliberately NO email / phone."""
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    languages = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Guide
        fields = ["id", "full_name", "languages", "is_active"]


class TranslationSerializer(serializers.Serializer):
    language_code = serializers.ChoiceField(choices=["en", "ru", "kk"])
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, required=False, default="")


class AdminTourSerializer(serializers.ModelSerializer):
    destination = serializers.PrimaryKeyRelatedField(queryset=Destination.objects.all())
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)       # CHECK >= 0
    duration_days = serializers.IntegerField(min_value=1)                                      # CHECK > 0
    translations = TranslationSerializer(many=True)
    title = serializers.SerializerMethodField()                                                # for list screens
    destination_name = serializers.CharField(source="destination.name", read_only=True)

    class Meta:
        model = TourPackage
        fields = ["id", "title", "destination", "destination_name", "base_price", "duration_days",
                  "accommodation_included", "transport_included", "is_active", "translations"]
        read_only_fields = ["is_active"]       # changed only by the deactivate / activate actions (audit-logged)

    def get_title(self, obj):
        t = pick_translation(obj.translations.all(), self.context.get("lang", "en"))
        return t.title if t else f"#{obj.pk}"

    def validate_translations(self, value):
        codes = [t["language_code"] for t in value]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("Each language may appear only once.", code="invalid")
        if "en" not in codes:
            raise serializers.ValidationError("An English title is required.", code="required")
        return value

    @transaction.atomic
    def create(self, validated):
        translations = validated.pop("translations")
        package = TourPackage.objects.create(**validated)
        for t in translations:
            PackageTranslation.objects.create(package=package, **t)
        return package

    @transaction.atomic
    def update(self, instance, validated):
        translations = validated.pop("translations", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        for t in translations or []:                      # upsert per language; missing languages are kept
            PackageTranslation.objects.update_or_create(package=instance, language_code=t["language_code"],
                                                        defaults={"title": t["title"], "description": t.get("description", "")})
        return instance


class AdminDepartureSerializer(serializers.ModelSerializer):
    package_title = serializers.SerializerMethodField()
    guide_name = serializers.CharField(source="guide.user.full_name", read_only=True)
    booked_seats = serializers.SerializerMethodField()

    class Meta:
        model = Departure
        fields = ["id", "package", "package_title", "guide", "guide_name", "start_at", "end_at",
                  "seats_total", "seats_available", "booked_seats", "is_active"]
        read_only_fields = ["seats_available", "is_active"]
        extra_kwargs = {"seats_total": {"min_value": 1}}

    def get_package_title(self, obj):
        t = pick_translation(obj.package.translations.all(), self.context.get("lang", "en"))
        return t.title if t else f"#{obj.package_id}"

    def get_booked_seats(self, obj):
        return obj.seats_total - obj.seats_available

    def validate(self, attrs):
        inst = self.instance
        start = attrs.get("start_at", inst.start_at if inst else None)
        end = attrs.get("end_at", inst.end_at if inst else None)
        errors = {}
        if start and end and end <= start:
            errors["end_at"] = [serializers.ErrorDetail("End must be after start.", code="invalid")]
        if inst is None and start and start <= timezone.now():
            errors["start_at"] = [serializers.ErrorDetail("The start must be in the future.", code="invalid")]
        guide = attrs.get("guide", inst.guide if inst else None)
        if guide is not None and not guide.is_active and (inst is None or guide.pk != inst.guide_id):
            errors["guide"] = [serializers.ErrorDetail("This guide is not active.", code="invalid")]
        package = attrs.get("package", inst.package if inst else None)
        if package is not None and not package.is_active and (inst is None or package.pk != inst.package_id):
            errors["package"] = [serializers.ErrorDetail("This tour is not active.", code="invalid")]
        if errors:
            raise serializers.ValidationError(errors)

        if inst is not None:
            booked = inst.seats_total - inst.seats_available
            new_total = attrs.get("seats_total", inst.seats_total)
            if new_total < booked:
                raise serializers.ValidationError({"seats_total": [serializers.ErrorDetail(
                    f"{booked} seats are already booked.", code="min_value")]})
            changed_core = any(k in attrs and attrs[k] != getattr(inst, k) for k in ("package", "guide", "start_at", "end_at"))
            if changed_core and Booking.objects.filter(departure=inst, status__in=Booking.ACTIVE).exists():
                raise ApiError("departure_has_bookings", "errors.departure.has_bookings",
                               "This departure has active bookings; tour, guide and time cannot be changed.", 409)

        # BR-01 in the service layer (PostgreSQL's EXCLUDE constraint is the backstop). Friendly error + next slot.
        if inst is None or inst.is_active:
            assert_no_guide_overlap(guide.pk, start, end, exclude_departure_id=inst.pk if inst else None)
        return attrs

    @transaction.atomic
    def create(self, validated):
        validated["seats_available"] = validated["seats_total"]          # a new departure is empty
        return Departure.objects.create(**validated)

    @transaction.atomic
    def update(self, instance, validated):
        booked = instance.seats_total - instance.seats_available
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.seats_available = instance.seats_total - booked          # keep the booked seats booked
        instance.save()
        return instance
