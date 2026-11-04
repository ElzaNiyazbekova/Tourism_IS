"""
Public catalogue endpoints (no login needed).   Owner: Aitore (Application & Development)

GET /api/destinations
GET /api/tours?destination=&price_min=&price_max=&date_from=&date_to=&guide_lang=&ordering=&lang=
GET /api/tours/<id>?lang=
"""
from datetime import datetime, timedelta

from django.db.models import Avg, Count, Exists, F, FloatField, IntegerField, OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from core.exceptions import ApiError
from core.lang import request_lang

from .models import Departure, Destination, Review, TourPackage
from .serializers import DestinationSerializer, TourDetailSerializer, TourListSerializer

ORDERINGS = {          # whitelist: never pass user input straight to order_by()
    "price": ("base_price",), "-price": ("-base_price",),
    "duration": ("duration_days",), "-duration": ("-duration_days",),
    "next": (F("next_departure_at").asc(nulls_last=True),),     # tours without a free departure go last
    "rating": (F("avg_rating").desc(nulls_last=True),),
}


def _bad_param(name):
    return ApiError("validation_error", "errors.validation", f"Invalid value for {name}.", 400,
                    field_errors={name: [{"message_key": "errors.field.invalid", "message": "Invalid value."}]})


def _parse_date(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return timezone.make_aware(datetime.strptime(raw, "%Y-%m-%d"))
    except ValueError:
        raise _bad_param(name)


def _parse_decimal(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise _bad_param(name)


def base_tour_queryset():
    """Active packages + 3 annotations computed with sub-queries (no joins => no duplicated rows)."""
    next_open = (Departure.objects.filter(package=OuterRef("pk"), start_at__gt=timezone.now(), seats_available__gt=0)
                 .order_by("start_at").values("start_at")[:1])
    rating = Review.objects.filter(package=OuterRef("pk")).values("package").annotate(a=Avg("rating"), c=Count("pk"))
    return (
        TourPackage.objects.filter(is_active=True)
        .select_related("destination")
        .prefetch_related("translations")
        .annotate(
            next_departure_at=Subquery(next_open),
            avg_rating=Subquery(rating.values("a")[:1], output_field=FloatField()),
            review_count=Coalesce(Subquery(rating.values("c")[:1], output_field=IntegerField()), Value(0)),
        )
    )


class DestinationListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DestinationSerializer
    queryset = Destination.objects.order_by("name")


class TourListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = TourListSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    @extend_schema(parameters=[OpenApiParameter(n, str, description=d) for n, d in [
        ("destination", "destination id"), ("price_min", "min base price"), ("price_max", "max base price"),
        ("date_from", "YYYY-MM-DD: has a departure on/after"), ("date_to", "YYYY-MM-DD: has a departure on/before"),
        ("guide_lang", "en|ru|kk: guide speaks it"), ("ordering", "price|-price|duration|-duration|next|rating"),
        ("lang", "en|ru|kk: language of title/description")]])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        p = self.request.query_params
        qs = base_tour_queryset()

        if p.get("destination"):
            if not p["destination"].isdigit():
                raise _bad_param("destination")
            qs = qs.filter(destination_id=int(p["destination"]))
        price_min, price_max = _parse_decimal(self.request, "price_min"), _parse_decimal(self.request, "price_max")
        if price_min is not None:
            qs = qs.filter(base_price__gte=price_min)
        if price_max is not None:
            qs = qs.filter(base_price__lte=price_max)

        # date / guide-language filters look at the package's FUTURE departures
        date_from, date_to, guide_lang = _parse_date(self.request, "date_from"), _parse_date(self.request, "date_to"), p.get("guide_lang")
        if date_from or date_to or guide_lang:
            deps = Departure.objects.filter(package=OuterRef("pk"), start_at__gt=timezone.now())
            if date_from:
                deps = deps.filter(start_at__gte=date_from)
            if date_to:
                deps = deps.filter(start_at__lt=date_to + timedelta(days=1))   # whole last day included
            if guide_lang in ("en", "ru", "kk"):
                deps = deps.filter(guide__languages_spoken__icontains=guide_lang)
            qs = qs.filter(Exists(deps))

        return qs.order_by(*ORDERINGS.get(p.get("ordering", ""), ()), "id")


class TourDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = TourDetailSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    def get_queryset(self):
        upcoming = Departure.objects.filter(start_at__gt=timezone.now()).select_related("guide__user").order_by("start_at")
        reviews = Review.objects.select_related("user").order_by("-created_at")[:20]
        return base_tour_queryset().prefetch_related(
            Prefetch("departures", queryset=upcoming, to_attr="upcoming_departures"),
            Prefetch("reviews", queryset=reviews, to_attr="recent_reviews"),
        )
