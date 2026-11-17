"""
Audit-log viewer (Task 7 governance).   Owner: Amina A. (Architecture & Security)

GET /api/admin/audit-log?table=&action=&user=&record=&date_from=&date_to=&page=
READ-ONLY on purpose: there is no POST / PATCH / DELETE, so the log cannot be edited through the API.
Admin only (it shows who changed what). Shows the user's name and role, never email or phone.
"""
from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.response import Response

from core.exceptions import ApiError
from core.permissions import role_required

from .models import AuditLog


class AuditUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    role = serializers.CharField(source="role.name")


class AuditLogSerializer(serializers.ModelSerializer):
    user = AuditUserSerializer(read_only=True, allow_null=True)      # null = done by the system (seed, jobs)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "action", "table_name", "record_id", "user", "old_value", "new_value"]


def _bad(name):
    return ApiError("validation_error", "errors.validation", f"Invalid value for {name}.", 400,
                    field_errors={name: [{"message_key": "errors.field.invalid", "message": "Invalid value."}]})


def _int(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    if not raw.isdigit():
        raise _bad(name)
    return int(raw)


def _date(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return timezone.make_aware(datetime.strptime(raw, "%Y-%m-%d"))
    except ValueError:
        raise _bad(name)


class AuditLogListView(generics.ListAPIView):
    permission_classes = [role_required("admin")]
    serializer_class = AuditLogSerializer

    @extend_schema(parameters=[OpenApiParameter(n, str, description=d) for n, d in [
        ("table", "table name, e.g. bookings"), ("action", "create|update|activate|deactivate|status_change|..."),
        ("user", "id of the user who did it"), ("record", "id of the changed record"),
        ("date_from", "YYYY-MM-DD"), ("date_to", "YYYY-MM-DD (whole day included)")]])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        p = self.request.query_params
        qs = AuditLog.objects.select_related("user__role")
        if p.get("table"):
            qs = qs.filter(table_name=p["table"])
        if p.get("action"):
            qs = qs.filter(action=p["action"])
        user, record = _int(self.request, "user"), _int(self.request, "record")
        if user is not None:
            qs = qs.filter(user_id=user)
        if record is not None:
            qs = qs.filter(record_id=record)
        date_from, date_to = _date(self.request, "date_from"), _date(self.request, "date_to")
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lt=date_to + timedelta(days=1))
        return qs.order_by("-created_at", "-id")


class AuditLogFacetsView(generics.GenericAPIView):
    """Values for the filter dropdowns (what tables / actions exist in the log)."""
    permission_classes = [role_required("admin")]
    serializer_class = None
    pagination_class = None

    @extend_schema(responses={200: dict})
    def get(self, request):
        base = AuditLog.objects
        return Response({"tables": list(base.order_by("table_name").values_list("table_name", flat=True).distinct()),
                         "actions": list(base.order_by("action").values_list("action", flat=True).distinct())})
