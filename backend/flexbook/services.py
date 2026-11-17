"""
FlexBook business rules.   Owner: Amina A. (Architecture & Security / transactions)

Same pattern as bookings/services.py: ONE transaction per action, row locks, audit row inside the transaction.
Lock order is always  booking -> departure  (create_booking locks only the departure, pay_booking only the
booking), so these functions cannot deadlock with the existing ones.

  cancel_booking     tourist cancels up to CANCEL_MIN_DAYS_BEFORE (3) days before start     (plan: Cancellation)
  undo_cancel        feature U3: 10-minute "I changed my mind" window after cancelling
  initiate/accept/decline/withdraw_handover   feature U4: pass your seat to a friend
  expire_overdue     48 h unpaid -> expired (called by `manage.py expire_bookings`)         (plan: expire job)
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from bookings.audit import audit
from bookings.models import AuditLog, Booking, Notification
from bookings.services import _rejected
from catalog.models import Departure
from core.exceptions import ApiError

from .models import SeatTransfer


def _undo_minutes():
    return getattr(settings, "CANCEL_UNDO_MINUTES", 10)


def _handover_hours():
    return getattr(settings, "HANDOVER_OFFER_HOURS", 24)


def _iso(dt):
    return dt.isoformat() if dt else None


def _lock_booking(user, booking_id):
    try:
        return (Booking.objects.select_for_update(of=("self",))
                .select_related("departure__guide__user").get(pk=booking_id, user=user))
    except Booking.DoesNotExist:
        raise ApiError("booking_not_found", "errors.booking.not_found", "Booking not found.", 404)


def _lock_departure(departure_id):
    return Departure.objects.select_for_update(of=("self",)).select_related("package", "guide__user").get(pk=departure_id)


def _notify(user, booking, type_, key, **params):
    Notification.objects.create(user=user, booking=booking, type=type_, message_key=key, params=params)


def _mask(email):
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


def _withdraw_open_offers(booking, now, why, actor=None):
    for t in SeatTransfer.objects.filter(booking=booking, status=SeatTransfer.PENDING):
        t.status, t.resolved_at = SeatTransfer.WITHDRAWN, now
        t.save(update_fields=["status", "resolved_at"])
        audit(actor, "handover_withdrawn", "bookings", booking.pk, {"transfer": t.pk}, {"reason": why})


# --------------------------------------------------------------------------------------- cancellation
def cancel_deadline(departure):
    return departure.start_at - timedelta(days=settings.CANCEL_MIN_DAYS_BEFORE)


def cancel_preview(user, booking_id):
    """Read-only "what happens if I cancel?" - the screen shows this before the tourist confirms."""
    try:
        b = Booking.objects.select_related("departure").get(pk=booking_id, user=user)
    except Booking.DoesNotExist:
        raise ApiError("booking_not_found", "errors.booking.not_found", "Booking not found.", 404)
    now = timezone.now()
    deadline = cancel_deadline(b.departure)
    reason = None
    if b.status not in Booking.ACTIVE:
        reason = "errors.cancel.not_cancellable"
    elif now > deadline:
        reason = "errors.cancel.too_late"
    return {"allowed": reason is None, "reason_key": reason, "deadline": deadline,
            "seats_returned": b.travelers_count, "was_paid": b.status == Booking.CONFIRMED,
            "undo_minutes": _undo_minutes(),
            "handover_possible": b.status in Booking.ACTIVE and b.departure.start_at > now}


def cancel_booking(user, booking_id):
    with transaction.atomic():
        booking = _lock_booking(user, booking_id)
        dep = _lock_departure(booking.departure_id)
        now = timezone.now()

        if booking.status not in Booking.ACTIVE:
            raise ApiError("not_cancellable", "errors.cancel.not_cancellable",
                           "Only a Pending or Confirmed booking can be cancelled.", 409)
        deadline = cancel_deadline(dep)
        if now > deadline:
            raise ApiError("cancel_too_late", "errors.cancel.too_late",
                           f"Cancellation is only possible up to {settings.CANCEL_MIN_DAYS_BEFORE} days before the start.",
                           409, extra={"cancel_deadline": _iso(deadline), "handover_available": dep.start_at > now})

        old = {"status": booking.status, "expires_at": _iso(booking.expires_at),
               "seats_available": dep.seats_available}
        dep.seats_available = min(dep.seats_total, dep.seats_available + booking.travelers_count)
        dep.save(update_fields=["seats_available"])

        booking.status, booking.expires_at = Booking.CANCELLED, None
        booking.save(update_fields=["status", "expires_at"])
        _withdraw_open_offers(booking, now, "booking_cancelled", actor=user)

        undo_until = now + timedelta(minutes=_undo_minutes())
        audit(user, "cancel", "bookings", booking.pk, old,
              {"status": booking.status, "seats_returned": booking.travelers_count, "undo_until": _iso(undo_until)})
        _notify(user, booking, "cancelled", "notifications.cancelled", ref=booking.booking_ref)
        _notify(dep.guide.user, booking, "cancelled", "notifications.guide_cancelled",
                ref=booking.booking_ref, seats=booking.travelers_count, start_at=_iso(dep.start_at))
    return booking, undo_until


def undo_cancel(user, booking_id):
    try:
        with transaction.atomic():
            booking = _lock_booking(user, booking_id)
            now = timezone.now()
            last = AuditLog.objects.filter(table_name="bookings", record_id=booking.pk).order_by("-id").first()
            if (booking.status != Booking.CANCELLED or last is None or last.action != "cancel"
                    or last.user_id != user.pk):
                raise ApiError("undo_not_available", "errors.undo.not_available",
                               "This booking was not cancelled by you just now.", 409)
            until = datetime.fromisoformat((last.new_value or {}).get("undo_until", "1970-01-01T00:00:00+00:00"))
            if until <= now:
                raise ApiError("undo_window_closed", "errors.undo.window_closed",
                               "The undo window has closed.", 409)

            dep = _lock_departure(booking.departure_id)
            if not (dep.is_active and dep.package.is_active and dep.guide.is_active):
                raise ApiError("undo_not_available", "errors.undo.not_available", "This departure is no longer open.", 409)
            if dep.start_at <= now:
                raise _rejected("departure_in_past", "errors.booking.departure_in_past",
                                "This departure has already started.", 422, dep, booking.travelers_count)
            if Booking.objects.filter(user=user, departure=dep, status__in=Booking.ACTIVE).exists():
                raise ApiError("duplicate_booking", "errors.booking.duplicate", "You already booked this departure.", 409)
            if dep.seats_available < booking.travelers_count:
                # somebody grabbed the seats in the meantime
                raise _rejected("departure_full", "errors.booking.departure_full",
                                "The seats were taken in the meantime.", 409, dep, booking.travelers_count)

            previous = (last.old_value or {}).get("status", Booking.PENDING)
            expires = None
            if previous == Booking.PENDING:
                raw = (last.old_value or {}).get("expires_at")
                expires = datetime.fromisoformat(raw) if raw else None
                if expires is not None and expires <= now:
                    raise ApiError("booking_expired", "errors.payment.expired",
                                   "The payment time (48 hours) has run out.", 409)

            dep.seats_available -= booking.travelers_count
            dep.save(update_fields=["seats_available"])
            booking.status, booking.expires_at = previous, expires
            booking.save(update_fields=["status", "expires_at"])
            audit(user, "cancel_undo", "bookings", booking.pk, {"status": Booking.CANCELLED},
                  {"status": previous, "expires_at": _iso(expires), "seats_taken": booking.travelers_count})
            _notify(user, booking, "restored", "notifications.restored", ref=booking.booking_ref)
            return booking
    except IntegrityError:
        raise ApiError("duplicate_booking", "errors.booking.duplicate", "You already booked this departure.", 409)


# --------------------------------------------------------------------------------------- seat handover
def initiate_handover(user, booking_id, email, message=""):
    from accounts.models import User

    email = email.strip().lower()
    try:
        with transaction.atomic():
            booking = _lock_booking(user, booking_id)
            now = timezone.now()
            if booking.status not in Booking.ACTIVE:
                raise ApiError("handover_not_allowed", "errors.handover.not_allowed",
                               "Only a Pending or Confirmed booking can be handed over.", 409)
            if booking.departure.start_at <= now:
                raise ApiError("departure_in_past", "errors.booking.departure_in_past",
                               "This departure has already started.", 409)
            if email == user.email.lower():
                raise ApiError("validation_error", "errors.validation", "Please correct the highlighted fields.", 400,
                               field_errors={"email": [{"message_key": "errors.handover.self",
                                                        "message": "You cannot hand a seat to yourself."}]})
            if SeatTransfer.objects.filter(booking=booking, status=SeatTransfer.PENDING, expires_at__gt=now).exists():
                raise ApiError("handover_exists", "errors.handover.exists", "There is already an open offer.", 409)
            # an old, already-timed-out offer must not block a new one (partial unique index covers 'pending')
            SeatTransfer.objects.filter(booking=booking, status=SeatTransfer.PENDING, expires_at__lte=now).update(
                status=SeatTransfer.EXPIRED, resolved_at=now)

            expires = min([now + timedelta(hours=_handover_hours()), booking.departure.start_at]
                          + ([booking.expires_at] if booking.expires_at else []))
            t = SeatTransfer.objects.create(booking=booking, from_user=user, to_email=email,
                                            message=message[:200], expires_at=expires)
            audit(user, "handover_offer", "bookings", booking.pk, None,
                  {"transfer": t.pk, "to": _mask(email), "expires_at": _iso(expires)})
            receiver = User.objects.filter(email__iexact=email, role__name="tourist").first()
            if receiver:
                _notify(receiver, booking, "handover_offer", "notifications.handover_offer",
                        **{"from": user.full_name, "ref": booking.booking_ref, "transfer": t.pk})
            return t
    except IntegrityError:
        raise ApiError("handover_exists", "errors.handover.exists", "There is already an open offer.", 409)


def _lock_transfer(transfer_id):
    try:
        return SeatTransfer.objects.select_for_update(of=("self",)).select_related("from_user").get(pk=transfer_id)
    except SeatTransfer.DoesNotExist:
        raise ApiError("handover_not_found", "errors.handover.not_found", "Offer not found.", 404)


def _for_receiver(user, transfer_id):
    t = _lock_transfer(transfer_id)
    if t.to_email.lower() != user.email.lower():
        raise ApiError("handover_not_found", "errors.handover.not_found", "Offer not found.", 404)   # 404, not 403: no leak
    return t


def accept_handover(user, transfer_id):
    try:
        with transaction.atomic():
            t = _for_receiver(user, transfer_id)
            now = timezone.now()
            if t.status != SeatTransfer.PENDING or t.expires_at <= now:
                raise ApiError("handover_closed", "errors.handover.closed", "This offer is no longer open.", 409)
            booking = (Booking.objects.select_for_update(of=("self",)).select_related("departure")
                       .get(pk=t.booking_id))
            if booking.status not in Booking.ACTIVE or booking.user_id != t.from_user_id:
                raise ApiError("handover_closed", "errors.handover.closed", "This offer is no longer open.", 409)
            if booking.departure.start_at <= now:
                raise ApiError("departure_in_past", "errors.booking.departure_in_past",
                               "This departure has already started.", 409)
            if Booking.objects.filter(user=user, departure=booking.departure, status__in=Booking.ACTIVE).exists():
                raise ApiError("duplicate_booking", "errors.booking.duplicate", "You already booked this departure.", 409)

            booking.user = user
            booking.save(update_fields=["user"])
            t.status, t.to_user, t.resolved_at = SeatTransfer.ACCEPTED, user, now
            t.save(update_fields=["status", "to_user", "resolved_at"])
            audit(user, "handover", "bookings", booking.pk, {"user": t.from_user_id},
                  {"user": user.pk, "transfer": t.pk, "status": booking.status})
            _notify(t.from_user, booking, "handover_accepted", "notifications.handover_accepted",
                    ref=booking.booking_ref, to=user.full_name)
            _notify(user, booking, "handover_received", "notifications.handover_received", ref=booking.booking_ref)
            return booking
    except IntegrityError:
        raise ApiError("duplicate_booking", "errors.booking.duplicate", "You already booked this departure.", 409)


def decline_handover(user, transfer_id):
    with transaction.atomic():
        t = _for_receiver(user, transfer_id)
        now = timezone.now()
        if t.status != SeatTransfer.PENDING:
            raise ApiError("handover_closed", "errors.handover.closed", "This offer is no longer open.", 409)
        t.status, t.to_user, t.resolved_at = SeatTransfer.DECLINED, user, now
        t.save(update_fields=["status", "to_user", "resolved_at"])
        audit(user, "handover_declined", "bookings", t.booking_id, {"transfer": t.pk}, {"status": t.status})
        _notify(t.from_user, t.booking, "handover_declined", "notifications.handover_declined", ref=t.booking.booking_ref)
        return t


def withdraw_handover(user, transfer_id):
    with transaction.atomic():
        t = _lock_transfer(transfer_id)
        if t.from_user_id != user.pk:
            raise ApiError("handover_not_found", "errors.handover.not_found", "Offer not found.", 404)
        if t.status != SeatTransfer.PENDING:
            raise ApiError("handover_closed", "errors.handover.closed", "This offer is no longer open.", 409)
        t.status, t.resolved_at = SeatTransfer.WITHDRAWN, timezone.now()
        t.save(update_fields=["status", "resolved_at"])
        audit(user, "handover_withdrawn", "bookings", t.booking_id, {"transfer": t.pk}, {"status": t.status})
        return t


# --------------------------------------------------------------------------------------- expiry job
def expire_overdue(now=None, dry_run=False):
    """
    Plan task: "an old Pending booking is expired by the command" (rule 7: 48 h unpaid).
    Each booking is its own small transaction, so one problem row never blocks the rest, and the command is
    safe to run every few minutes or twice at the same time (the second run finds nothing left to do).
    """
    now = now or timezone.now()
    result = {"bookings_expired": [], "seats_returned": 0, "offers_expired": 0}

    candidates = list(Booking.objects.filter(status=Booking.PENDING, expires_at__isnull=False, expires_at__lte=now)
                      .order_by("expires_at").values_list("pk", "booking_ref", "travelers_count"))
    for pk, ref, seats in candidates:
        if dry_run:
            result["bookings_expired"].append(ref)
            result["seats_returned"] += seats
            continue
        with transaction.atomic():
            b = (Booking.objects.select_for_update(of=("self",)).select_related("user", "departure__guide__user")
                 .get(pk=pk))
            if b.status != Booking.PENDING or b.expires_at is None or b.expires_at > now:
                continue                                    # paid / cancelled / extended since we looked
            dep = _lock_departure(b.departure_id)
            old = {"status": b.status, "expires_at": _iso(b.expires_at)}
            dep.seats_available = min(dep.seats_total, dep.seats_available + b.travelers_count)
            dep.save(update_fields=["seats_available"])
            b.status = Booking.CANCELLED
            b.save(update_fields=["status"])                # expires_at stays: it records WHEN it ran out
            _withdraw_open_offers(b, now, "booking_expired")
            audit(None, "expire", "bookings", b.pk, old,
                  {"status": b.status, "reason": "unpaid_48h", "seats_returned": b.travelers_count})
            _notify(b.user, b, "expired", "notifications.expired", ref=b.booking_ref)
            _notify(dep.guide.user, b, "expired", "notifications.guide_expired",
                    ref=b.booking_ref, seats=b.travelers_count, start_at=_iso(dep.start_at))
            result["bookings_expired"].append(b.booking_ref)
            result["seats_returned"] += b.travelers_count

    stale = SeatTransfer.objects.filter(status=SeatTransfer.PENDING, expires_at__lte=now)
    if dry_run:
        result["offers_expired"] = stale.count()
    else:
        for t in list(stale.select_related("booking", "from_user")):
            with transaction.atomic():
                t = SeatTransfer.objects.select_for_update(of=("self",)).get(pk=t.pk)
                if t.status != SeatTransfer.PENDING:
                    continue
                t.status, t.resolved_at = SeatTransfer.EXPIRED, now
                t.save(update_fields=["status", "resolved_at"])
                audit(None, "handover_expired", "bookings", t.booking_id, {"transfer": t.pk}, {"status": t.status})
                _notify(t.from_user, t.booking, "handover_expired", "notifications.handover_expired",
                        ref=t.booking.booking_ref)
                result["offers_expired"] += 1
    return result
