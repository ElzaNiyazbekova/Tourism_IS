"""
Analyst view: AGGREGATE-ONLY report (counts and money per package). No names, emails or phones.
Owner: Dastan (Analytics) / Amina A. (role limits)

Same numbers as the SQL view analyst_booking_view:
  active    = bookings in Pending or Confirmed (the Task 9 definition)
  completed = Completed,  cancelled = Cancelled
  revenue   = sum of SUCCESSFUL payments for the package's bookings
Packages with zero bookings still appear with 0 (like the LEFT JOIN query in db/analytics.sql).
"""
from decimal import Decimal

from django.db.models import Count, Sum
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import TourPackage
from core.lang import pick_translation, request_lang
from core.permissions import role_required

from .models import Booking, Payment


def package_report(lang="en"):
    counts = {}
    for row in (Booking.objects.values("departure__package_id", "status").annotate(n=Count("id"))):
        counts[(row["departure__package_id"], row["status"])] = row["n"]
    revenue = {row["booking__departure__package_id"]: row["total"] for row in
               Payment.objects.filter(status=Payment.SUCCESS).values("booking__departure__package_id")
               .annotate(total=Sum("amount"))}

    rows = []
    for p in TourPackage.objects.select_related("destination").prefetch_related("translations").order_by("id"):
        t = pick_translation(p.translations.all(), lang)
        rows.append({
            "package_id": p.pk,
            "title": t.title if t else f"#{p.pk}",
            "destination": p.destination.name,
            "is_active": p.is_active,
            "active_bookings": counts.get((p.pk, "Pending"), 0) + counts.get((p.pk, "Confirmed"), 0),
            "completed_bookings": counts.get((p.pk, "Completed"), 0),
            "cancelled_bookings": counts.get((p.pk, "Cancelled"), 0),
            "revenue": str((revenue.get(p.pk) or Decimal("0")).quantize(Decimal("0.01"))),
        })
    totals = {
        "active_bookings": sum(r["active_bookings"] for r in rows),
        "completed_bookings": sum(r["completed_bookings"] for r in rows),
        "cancelled_bookings": sum(r["cancelled_bookings"] for r in rows),
        "revenue": str(sum((Decimal(r["revenue"]) for r in rows), Decimal("0")).quantize(Decimal("0.01"))),
    }
    return {"packages": rows, "totals": totals}


class PackageReportView(APIView):
    """GET /api/analytics/packages?lang=  - analyst, manager and admin only."""
    permission_classes = [role_required("analyst", "manager", "admin")]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(package_report(request_lang(request)))
