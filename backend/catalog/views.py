"""
Public catalogue endpoints (no login needed).   Owner: Aitore (Application & Development)

GET /api/destinations
GET /api/tours?q=&destination=&price_min=&price_max=&duration_min=&duration_max=&date_from=&date_to=&guide_lang=
               &accommodation=1&transport=1&rating_min=&available=1&ordering=&lang=
GET /api/tours/<id>?lang=
GET /api/guides/<id>?lang=          public guide profile (no email/phone)
"""
from datetime import datetime, timedelta

from django.db.models import Avg, Count, Q, Exists, F, FloatField, IntegerField, OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from core.exceptions import ApiError
from core.lang import request_lang

from accounts.models import Guide

from .models import Departure, Destination, PackageTranslation, Review, TourPackage, TourPhoto
from .serializers import DestinationSerializer, GuideProfileSerializer, TourDetailSerializer, TourListSerializer

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


def _parse_int(request, name, lo=0, hi=10_000):
    raw = request.query_params.get(name)
    if not raw:
        return None
    if not raw.isdigit() or not lo <= int(raw) <= hi:
        raise _bad_param(name)
    return int(raw)


def _flag(request, name):
    return request.query_params.get(name, "").lower() in ("1", "true", "yes")


def base_tour_queryset():
    """Active packages + 3 annotations computed with sub-queries (no joins => no duplicated rows)."""
    next_open = (Departure.objects.filter(package=OuterRef("pk"), is_active=True, start_at__gt=timezone.now(), seats_available__gt=0)
                 .order_by("start_at").values("start_at")[:1])
    rating = Review.objects.filter(package=OuterRef("pk")).values("package").annotate(a=Avg("rating"), c=Count("pk"))
    cover = TourPhoto.objects.filter(package=OuterRef("pk")).order_by("sort_order", "id").values("id")[:1]
    return (
        TourPackage.objects.filter(is_active=True)
        .select_related("destination")
        .prefetch_related("translations")
        .annotate(
            next_departure_at=Subquery(next_open),
            avg_rating=Subquery(rating.values("a")[:1], output_field=FloatField()),
            review_count=Coalesce(Subquery(rating.values("c")[:1], output_field=IntegerField()), Value(0)),
            cover_photo_id=Subquery(cover),
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
        ("q", "text search in title/description (any language)"),
        ("destination", "destination id"), ("price_min", "min base price"), ("price_max", "max base price"),
        ("date_from", "YYYY-MM-DD: has a departure on/after"), ("date_to", "YYYY-MM-DD: has a departure on/before"),
        ("duration_min", "min days"), ("duration_max", "max days"),
        ("accommodation", "1: accommodation included"), ("transport", "1: transport included"),
        ("rating_min", "1-5: average rating at least"), ("available", "1: has an upcoming departure with free seats"),
        ("guide_lang", "en|ru|kk: guide speaks it"), ("ordering", "price|-price|duration|-duration|next|rating"),
        ("lang", "en|ru|kk: language of title/description")]])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        p = self.request.query_params
        qs = base_tour_queryset()

        search = p.get("q", "").strip()[:100]
        if search:   # Exists sub-query: a match in several languages must not duplicate the tour
            matches = PackageTranslation.objects.filter(package=OuterRef("pk")).filter(
                Q(title__icontains=search) | Q(description__icontains=search))
            qs = qs.filter(Q(Exists(matches)) | Q(destination__name__icontains=search))

        if p.get("destination"):
            if not p["destination"].isdigit():
                raise _bad_param("destination")
            qs = qs.filter(destination_id=int(p["destination"]))
        price_min, price_max = _parse_decimal(self.request, "price_min"), _parse_decimal(self.request, "price_max")
        if price_min is not None:
            qs = qs.filter(base_price__gte=price_min)
        if price_max is not None:
            qs = qs.filter(base_price__lte=price_max)
        duration_min, duration_max = _parse_int(self.request, "duration_min"), _parse_int(self.request, "duration_max")
        if duration_min is not None:
            qs = qs.filter(duration_days__gte=duration_min)
        if duration_max is not None:
            qs = qs.filter(duration_days__lte=duration_max)
        if _flag(self.request, "accommodation"):
            qs = qs.filter(accommodation_included=True)
        if _flag(self.request, "transport"):
            qs = qs.filter(transport_included=True)
        rating_min = _parse_decimal(self.request, "rating_min")
        if rating_min is not None:
            if not 1 <= rating_min <= 5:
                raise _bad_param("rating_min")
            qs = qs.filter(avg_rating__gte=rating_min)
        if _flag(self.request, "available"):
            qs = qs.filter(next_departure_at__isnull=False)   # annotation = next future departure with free seats

        # date / guide-language filters look at the package's FUTURE departures
        date_from, date_to, guide_lang = _parse_date(self.request, "date_from"), _parse_date(self.request, "date_to"), p.get("guide_lang")
        if date_from or date_to or guide_lang:
            deps = Departure.objects.filter(package=OuterRef("pk"), is_active=True, start_at__gt=timezone.now())
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
        upcoming = Departure.objects.filter(is_active=True, start_at__gt=timezone.now()).select_related("guide__user").order_by("start_at")
        reviews = Review.objects.select_related("user").order_by("-created_at")[:20]
        return base_tour_queryset().prefetch_related(
            Prefetch("departures", queryset=upcoming, to_attr="upcoming_departures"),
            Prefetch("reviews", queryset=reviews, to_attr="recent_reviews"),
            Prefetch("photos", queryset=TourPhoto.objects.order_by("sort_order", "id"), to_attr="ordered_photos"),
        )


class GuideProfileView(generics.RetrieveAPIView):
    """Public profile of an active guide: bio, languages, how many tours led, next open departures."""
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = GuideProfileSerializer
    UPCOMING_LIMIT = 10

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    @extend_schema(parameters=[OpenApiParameter("lang", str, description="en|ru|kk: language of tour titles")])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        now = timezone.now()
        return Guide.objects.filter(is_active=True).select_related("user").annotate(
            completed_count=Count("departures", filter=Q(departures__is_active=True, departures__end_at__lte=now)))

    def get_object(self):
        guide = super().get_object()
        guide.upcoming_departures = list(
            Departure.objects.filter(guide=guide, is_active=True, package__is_active=True, start_at__gt=timezone.now())
            .select_related("package").prefetch_related("package__translations")
            .order_by("start_at")[: self.UPCOMING_LIMIT])
        return guide
