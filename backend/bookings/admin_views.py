"""Manager/admin booking list, statistics and exports. Owner: Aitore / Dastan"""
import csv
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from core.lang import pick_translation, request_lang
from core.permissions import IsStaffRole
from .audit import audit
from .models import AuditLog, Booking, Payment
from .services import expire_stale_pending_throttled


class AdminBookingPagination(PageNumberPagination):
    page_size = 20


def date_filtered(qs, date_from, date_to):
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


class AdminBookingsView(ListAPIView):
    permission_classes = [IsStaffRole]
    pagination_class = AdminBookingPagination

    def get_queryset(self):
        expire_stale_pending_throttled()
        lang = request_lang(self.request)
        qs = Booking.objects.select_related("user", "departure__package")
        qs = qs.prefetch_related("departure__package__translations")
        status = self.request.query_params.get("status")
        package = self.request.query_params.get("package")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        q = self.request.query_params.get("q")
        include_cancelled = self.request.query_params.get("include_cancelled", "false").lower() == "true"
        qs = date_filtered(qs, date_from, date_to)
        if status:
            qs = qs.filter(status=status)
        if package:
            qs = qs.filter(departure__package_id=package)
        if q:
            qs = qs.filter(Q(booking_ref__icontains=q) | Q(user__email__icontains=q) | Q(user__full_name__icontains=q))
        if not include_cancelled:
            qs = qs.exclude(status__in=[Booking.CANCELLED, Booking.EXPIRED])
            seen = set(); ordered = []
            for b in qs.order_by("-created_at", "-id"):
                key = (b.user_id, b.departure_id)
                if b.status in Booking.ACTIVE:
                    if key in seen:
                        continue
                    seen.add(key)
                ordered.append(b)
            ids = [b.id for b in ordered]
            return Booking.objects.filter(id__in=ids).select_related("user", "departure__package").prefetch_related("departure__package__translations").order_by("-created_at", "-id")
        return qs.order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = []
        lang = request_lang(request)
        for b in page:
            t = pick_translation(b.departure.package.translations.all(), lang)
            rows.append({"booking_ref":b.booking_ref,"tourist_name":b.user.full_name,"tourist_email":b.user.email,
                         "package_title":t.title if t else f"#{b.departure.package_id}","travel_date":b.travel_date,
                         "travelers_count":b.travelers_count,"total_cost":str(b.total_cost),"status":b.status,
                         "created_at":b.created_at})
        return self.get_paginated_response(rows)


class AdminStatsView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(responses={200: dict})
    def get(self, request):
        expire_stale_pending_throttled()
        qs = date_filtered(Booking.objects.all(), request.query_params.get("date_from"), request.query_params.get("date_to"))
        total = qs.count()
        revenue = Payment.objects.filter(status=Payment.SUCCESS, booking__in=qs).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        avg = (revenue / total).quantize(Decimal("0.01")) if total else Decimal("0.00")
        cancelled_expired = qs.filter(status__in=[Booking.CANCELLED, Booking.EXPIRED]).count()
        status_rows = list(qs.values("status").annotate(count=Count("id")).order_by("status"))
        monthly = []
        month_rows = list(qs.values("created_at__year", "created_at__month").annotate(count=Count("id")).order_by("created_at__year", "created_at__month"))
        for row in month_rows[-12:]:
            monthly.append({"month": f"{row['created_at__year']}-{row['created_at__month']:02d}", "count": row["count"]})
        pkg_rows = []
        for row in qs.values("departure__package_id").annotate(revenue=Sum("payments__amount", filter=Q(payments__status=Payment.SUCCESS))).order_by("-revenue")[:5]:
            pkg_id = row["departure__package_id"]
            from catalog.models import TourPackage
            p = TourPackage.objects.prefetch_related("translations").filter(pk=pkg_id).first()
            if p:
                t = pick_translation(p.translations.all(), request_lang(request)); title = t.title if t else f"#{pkg_id}"
            else:
                title = f"#{pkg_id}"
            pkg_rows.append({"package_id":pkg_id,"title":title,"revenue":str(row["revenue"] or Decimal("0"))})
        return Response({"totals":{"bookings":total,"revenue":str(revenue.quantize(Decimal("0.01"))),
                                  "average_booking_value":str(avg),"cancellation_expiry_rate":round(cancelled_expired/total,6) if total else 0,
                                  "cancellation_expiry_rate_label":"(Cancelled + Expired) / all bookings"},
                         "bookings_by_status":status_rows,"bookings_per_month":monthly,"top_packages_by_revenue":pkg_rows})


class AdminReportExportView(APIView):
    permission_classes = [IsStaffRole]

    @extend_schema(responses={200: {"type":"string","format":"binary"}})
    def get(self, request):
        expire_stale_pending_throttled()
        lang = request_lang(request)
        qs = date_filtered(Booking.objects.select_related("user","departure__package"), request.query_params.get("date_from"), request.query_params.get("date_to"))
        qs = qs.prefetch_related("departure__package__translations")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="tourism_report_{timezone.localdate().isoformat()}.csv"'
        response.write("\ufeff")
        w = csv.writer(response)
        w.writerow(["SUMMARY"])
        total = qs.count(); revenue = Payment.objects.filter(status=Payment.SUCCESS, booking__in=qs).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        w.writerow(["bookings",total]); w.writerow(["revenue",str(revenue)]); w.writerow(["average booking value",str((revenue/total).quantize(Decimal("0.01")) if total else Decimal("0.00"))])
        w.writerow(["PER PACKAGE"]); w.writerow(["package_id","title","revenue"])
        for row in qs.values("departure__package_id").annotate(revenue=Sum("payments__amount", filter=Q(payments__status=Payment.SUCCESS))).order_by("departure__package_id"):
            pkg_id=row["departure__package_id"]
            from catalog.models import TourPackage
            p=TourPackage.objects.prefetch_related("translations").filter(pk=pkg_id).first(); t=pick_translation(p.translations.all(),lang) if p else None
            w.writerow([pkg_id,t.title if t else f"#{pkg_id}",str(row["revenue"] or Decimal("0"))])
        w.writerow(["BOOKINGS"]); w.writerow(["booking_ref","tourist_name","tourist_email","package_title","travel_date","travelers_count","total_cost","status","created_at"])
        for b in qs.order_by("-created_at","-id"):
            t=pick_translation(b.departure.package.translations.all(),lang)
            w.writerow([b.booking_ref,b.user.full_name,b.user.email,t.title if t else f"#{b.departure.package_id}",b.travel_date,b.travelers_count,str(b.total_cost),b.status,b.created_at.isoformat()])
        audit(request.user,"report_export","bookings",None,None,{"format":"csv","date_from":request.query_params.get("date_from"),"date_to":request.query_params.get("date_to")})
        return response
