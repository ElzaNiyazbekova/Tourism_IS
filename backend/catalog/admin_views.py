"""
Staff CRUD (start): tours (+translations) and departures.  /api/admin/...   Owner: Aitore / Amina A. (permissions)

Only manager and admin (server-side `role_required`; the Angular guard is just convenience).
No DELETE on purpose: every foreign key is RESTRICT, so we DEACTIVATE instead (is_active = false).
Every create / edit / deactivate / activate writes a row to audit_log.
"""
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Guide
from bookings.audit import audit
from bookings.models import Booking
from core.exceptions import ApiError
from core.lang import request_lang
from core.permissions import role_required

from .admin_serializers import (AdminDepartureSerializer, AdminDestinationSerializer, AdminGuideSerializer,
                                AdminTourSerializer)
from .models import Departure, Destination, TourPackage
from .services import assert_no_guide_overlap, next_available_departure

STAFF = [role_required("manager", "admin")]


def _tour_snapshot(t):
    return {"destination": t.destination_id, "base_price": str(t.base_price), "duration_days": t.duration_days,
            "accommodation_included": t.accommodation_included, "transport_included": t.transport_included,
            "is_active": t.is_active}


def _dep_snapshot(d):
    return {"package": d.package_id, "guide": d.guide_id, "start_at": d.start_at.isoformat(), "end_at": d.end_at.isoformat(),
            "seats_total": d.seats_total, "seats_available": d.seats_available, "is_active": d.is_active}


def _overlap_error(guide_id):
    return ApiError("guide_overlap", "errors.departure.guide_overlap",
                    "This guide already has another departure at that time.", 409,
                    extra={"next_available_departure": next_available_departure(guide_id)})


class _AuditedWrite:
    """Mixin: audit-log every create / update of the model behind the view."""
    table = ""
    snapshot = staticmethod(lambda obj: {})

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                obj = serializer.save()
                audit(self.request.user, "create", self.table, obj.pk, None, self.snapshot(obj))
        except IntegrityError:        # the database rule (EXCLUDE) caught a race the service check missed
            raise _overlap_error(serializer.validated_data["guide"].pk)

    def perform_update(self, serializer):
        old = self.snapshot(serializer.instance)
        try:
            with transaction.atomic():
                obj = serializer.save()
                audit(self.request.user, "update", self.table, obj.pk, old, self.snapshot(obj))
        except IntegrityError:
            raise _overlap_error(serializer.instance.guide_id)


# ---------------- tours ----------------
class AdminTourListCreate(_AuditedWrite, generics.ListCreateAPIView):
    permission_classes = STAFF
    serializer_class = AdminTourSerializer
    table, snapshot = "tour_packages", staticmethod(_tour_snapshot)

    def get_queryset(self):
        qs = TourPackage.objects.select_related("destination").prefetch_related("translations").order_by("-id")
        active = self.request.query_params.get("active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=(active == "true"))
        return qs


class AdminTourDetail(_AuditedWrite, generics.RetrieveUpdateAPIView):
    permission_classes = STAFF
    serializer_class = AdminTourSerializer
    table, snapshot = "tour_packages", staticmethod(_tour_snapshot)
    queryset = TourPackage.objects.select_related("destination").prefetch_related("translations")


class _ToggleActive(APIView):
    """Shared code of deactivate / activate."""
    permission_classes = STAFF
    target = True       # the is_active value this endpoint sets

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, pk):
        with transaction.atomic():
            obj = self.lock(pk)
            old = self.snapshot(obj)
            self.before(obj)
            obj.is_active = self.target
            obj.save(update_fields=["is_active"])
            audit(request.user, "activate" if self.target else "deactivate", self.table, obj.pk, old, self.snapshot(obj))
        return Response(self.respond(request, obj))


class TourDeactivate(_ToggleActive):
    table, snapshot, target = "tour_packages", staticmethod(_tour_snapshot), False

    def lock(self, pk):
        try:
            return TourPackage.objects.select_for_update(of=("self",)).get(pk=pk)
        except TourPackage.DoesNotExist:
            raise ApiError("not_found", "errors.not_found", "Not found.", 404)

    def before(self, obj):
        pass   # existing bookings stay valid; the tour just disappears from the public list

    def respond(self, request, obj):
        obj = TourPackage.objects.select_related("destination").prefetch_related("translations").get(pk=obj.pk)
        return AdminTourSerializer(obj, context={"lang": request_lang(request)}).data


class TourActivate(TourDeactivate):
    target = True


# ---------------- departures ----------------
class AdminDepartureListCreate(_AuditedWrite, generics.ListCreateAPIView):
    permission_classes = STAFF
    serializer_class = AdminDepartureSerializer
    table, snapshot = "departures", staticmethod(_dep_snapshot)

    def get_queryset(self):
        qs = (Departure.objects.select_related("guide__user", "package").prefetch_related("package__translations")
              .order_by("-start_at", "-id"))
        p = self.request.query_params
        if p.get("active") in ("true", "false"):
            qs = qs.filter(is_active=(p["active"] == "true"))
        if p.get("package", "").isdigit():
            qs = qs.filter(package_id=int(p["package"]))
        return qs


class AdminDepartureDetail(_AuditedWrite, generics.RetrieveUpdateAPIView):
    permission_classes = STAFF
    serializer_class = AdminDepartureSerializer
    table, snapshot = "departures", staticmethod(_dep_snapshot)
    queryset = Departure.objects.select_related("guide__user", "package").prefetch_related("package__translations")


class DepartureDeactivate(_ToggleActive):
    table, snapshot, target = "departures", staticmethod(_dep_snapshot), False

    def lock(self, pk):
        try:
            return Departure.objects.select_for_update(of=("self",)).get(pk=pk)
        except Departure.DoesNotExist:
            raise ApiError("not_found", "errors.not_found", "Not found.", 404)

    def before(self, obj):
        if self.target is False and Booking.objects.filter(departure=obj, status__in=Booking.ACTIVE).exists():
            raise ApiError("departure_has_bookings", "errors.departure.has_bookings",
                           "This departure has active bookings and cannot be deactivated.", 409)
        if self.target is True:
            # the slot was free while inactive: make sure the guide is still free before switching it on again
            assert_no_guide_overlap(obj.guide_id, obj.start_at, obj.end_at, exclude_departure_id=obj.pk)

    def respond(self, request, obj):
        obj = (Departure.objects.select_related("guide__user", "package").prefetch_related("package__translations")
               .get(pk=obj.pk))
        return AdminDepartureSerializer(obj, context={"lang": request_lang(request)}).data


class DepartureActivate(DepartureDeactivate):
    target = True


# ---------------- small lookup lists for the forms ----------------
class AdminDestinationList(generics.ListAPIView):
    permission_classes = STAFF
    serializer_class = AdminDestinationSerializer
    queryset = Destination.objects.order_by("name")
    pagination_class = None


class AdminGuideList(generics.ListAPIView):
    permission_classes = STAFF
    serializer_class = AdminGuideSerializer
    queryset = Guide.objects.select_related("user").order_by("user__full_name")
    pagination_class = None
