"""
Catalogue business logic.   Owner: Amina A. (Architecture - transactions/locking)

assert_no_guide_overlap: the SQLite-fallback version of rule 2 (BR-01). On PostgreSQL the
EXCLUDE constraint already guarantees this, but calling it first gives a friendly error
(and the same behaviour on both databases).
next_available_departure: Lab 4 acceptance criterion - when a request is rejected we tell the
tourist the guide's NEXT free departure.
"""
from django.db import transaction
from django.utils import timezone

from core.exceptions import ApiError

from .models import Departure


def assert_no_guide_overlap(guide_id, start_at, end_at, exclude_departure_id=None):
    """Raise ApiError if the guide already has a departure overlapping [start_at, end_at)."""
    with transaction.atomic():
        qs = Departure.objects.select_for_update().filter(guide_id=guide_id, is_active=True, start_at__lt=end_at, end_at__gt=start_at)
        if exclude_departure_id:
            qs = qs.exclude(pk=exclude_departure_id)
        clash = qs.first()
    if clash:
        raise ApiError("guide_overlap", "errors.departure.guide_overlap",
                       "This guide already has another departure at that time.", 409,
                       extra={"next_available_departure": next_available_departure(guide_id)})


def next_available_departure(guide_id, min_seats=1, exclude_departure_id=None):
    """First future departure of this guide with enough free seats, or None."""
    qs = Departure.objects.filter(guide_id=guide_id, is_active=True, start_at__gt=timezone.now(), seats_available__gte=min_seats)
    if exclude_departure_id:
        qs = qs.exclude(pk=exclude_departure_id)
    dep = qs.order_by("start_at").first()
    if dep is None:
        return None
    return {"departure_id": dep.pk, "package_id": dep.package_id,
            "start_at": dep.start_at.isoformat(), "seats_available": dep.seats_available}
