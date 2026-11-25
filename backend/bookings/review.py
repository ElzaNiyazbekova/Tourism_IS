"""Staff actions for bookings that need manual review."""
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Departure
from .audit import audit
from .models import Booking, Payment
from core.exceptions import ApiError


def _lock_review_booking(pk):
    try:
        booking = (Booking.objects.select_for_update(of=("self",))
                   .select_related("user", "departure__package")
                   .get(pk=pk))
    except Booking.DoesNotExist:
        raise ApiError("booking_not_found", "errors.booking.not_found", "Booking not found.", 404)
    return booking


def _resolved_status(*bookings):
    ids = [booking.pk for booking in bookings]
    if Payment.objects.filter(booking_id__in=ids, status=Payment.SUCCESS).exists():
        return Booking.CONFIRMED
    return Booking.PENDING


def _ensure_no_active_duplicate(booking, exclude_ids):
    duplicate = (Booking.objects.filter(user_id=booking.user_id, departure_id=booking.departure_id,
                                        status__in=Booking.ACTIVE)
                 .exclude(pk__in=exclude_ids).exists())
    if duplicate:
        raise ApiError("booking_conflict", "errors.review.booking_conflict",
                       "An active booking already exists for this traveller and departure.", 409)


def fix_review_booking(actor, booking_id):
    """Resolve using payment evidence: successful payment -> Confirmed, otherwise Pending."""
    try:
        with transaction.atomic():
            booking = _lock_review_booking(booking_id)
            _ensure_no_active_duplicate(booking, [booking.pk])
            old = {"status": booking.status, "expires_at": booking.expires_at.isoformat() if booking.expires_at else None}
            booking.status = _resolved_status(booking)
            if booking.status == Booking.CONFIRMED:
                booking.expires_at = None
            else:
                booking.expires_at = timezone.now() + timedelta(hours=settings.PENDING_BOOKING_HOURS)
            booking.save(update_fields=["status", "expires_at"])
            audit(actor, "status_change", "bookings", booking.pk, old,
                  {"status": booking.status, "reason": "staff_review_fix", "expires_at": booking.expires_at.isoformat() if booking.expires_at else None})
            return booking
    except IntegrityError:
        raise ApiError("booking_conflict", "errors.review.booking_conflict",
                       "An active booking already exists for this traveller and departure.", 409)


def reject_review_booking(actor, booking_id):
    """Reject a review booking and release its held seats."""
    with transaction.atomic():
        booking = _lock_review_booking(booking_id)
        departure = Departure.objects.select_for_update(of=("self",)).get(pk=booking.departure_id)
        old = {"status": booking.status, "expires_at": booking.expires_at.isoformat() if booking.expires_at else None,
               "seats_available": departure.seats_available}
        released = max(0, min(booking.travelers_count, departure.seats_total - departure.seats_available))
        departure.seats_available += released
        departure.save(update_fields=["seats_available"])
        booking.status, booking.expires_at = Booking.CANCELLED, None
        booking.save(update_fields=["status", "expires_at"])
        audit(actor, "status_change", "bookings", booking.pk, old,
              {"status": booking.status, "reason": "staff_review_reject", "seats_returned": released})
        return booking


def merge_review_bookings(actor, source_id, target_id):
    """Merge source into target; only same-customer, same-departure review rows can be combined."""
    if source_id == target_id:
        raise ApiError("invalid_merge", "errors.review.invalid_merge", "Choose a different booking to merge into.", 400)

    try:
        with transaction.atomic():
            # Stable lock order avoids deadlocks when two staff members merge concurrently.
            locked = {b.pk: b for b in (Booking.objects.select_for_update(of=("self",))
                                          .select_related("user", "departure__package")
                                          .filter(pk__in=sorted([source_id, target_id])).order_by("pk"))}
            if source_id not in locked or target_id not in locked:
                raise ApiError("booking_not_found", "errors.booking.not_found", "Booking not found.", 404)
            source, target = locked[source_id], locked[target_id]
            if source.user_id != target.user_id or source.departure_id != target.departure_id:
                raise ApiError("invalid_merge", "errors.review.invalid_merge",
                               "Bookings can only be merged for the same traveller and departure.", 400)

            travelers = source.travelers_count + target.travelers_count
            if travelers > target.departure.seats_total or travelers > 50:
                raise ApiError("merge_capacity_exceeded", "errors.review.merge_capacity",
                               "The merged booking exceeds the departure capacity.", 409)
            _ensure_no_active_duplicate(target, [source.pk, target.pk])

            old_source = {"status": source.status, "travelers_count": source.travelers_count,
                          "total_cost": str(source.total_cost)}
            old_target = {"status": target.status, "travelers_count": target.travelers_count,
                          "total_cost": str(target.total_cost)}
            source_payments = list(Payment.objects.filter(booking_id=source.pk).values_list("pk", "transaction_ref"))
            Payment.objects.filter(pk__in=[payment_id for payment_id, _ in source_payments]).update(booking_id=target.pk)
            for payment_id, transaction_ref in source_payments:
                audit(actor, "booking_merge", "payments", payment_id,
                      {"booking": source.booking_ref, "transaction_ref": transaction_ref},
                      {"booking": target.booking_ref, "transaction_ref": transaction_ref})
            target.travelers_count = travelers
            target.total_cost += source.total_cost
            requests = [part for part in (target.special_request.strip(), source.special_request.strip()) if part]
            target.special_request = "\n".join(requests)[:500]
            target.status = _resolved_status(target, source)
            target.expires_at = (None if target.status == Booking.CONFIRMED else
                                 timezone.now() + timedelta(hours=settings.PENDING_BOOKING_HOURS))
            target.save(update_fields=["travelers_count", "total_cost", "special_request", "status", "expires_at"])
            source.status, source.expires_at = Booking.CANCELLED, None
            source.save(update_fields=["status", "expires_at"])

            audit(actor, "booking_merge", "bookings", target.pk, old_target,
                  {"status": target.status, "travelers_count": target.travelers_count,
                   "total_cost": str(target.total_cost), "merged_booking": source.booking_ref})
            audit(actor, "booking_merge", "bookings", source.pk, old_source,
                  {"status": source.status, "merged_into": target.booking_ref})
            return target
    except IntegrityError:
        raise ApiError("booking_conflict", "errors.review.booking_conflict",
                       "An active booking already exists for this traveller and departure.", 409)