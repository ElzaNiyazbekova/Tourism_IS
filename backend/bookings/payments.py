"""
Mock payment gateway + the payment transaction.   Owner: Aitore (payment mock) / Amina A. (transaction)

There is NO real money. The "gateway" is a function: the screen has two buttons,
"Pay" (-> Success) and "Fail" (-> Failed), and the gateway answers with a status and a transaction reference.

pay_booking is ONE transaction (Task 9 transaction, rule 10):
    lock the booking row -> checks -> ask gateway -> insert payments row -> (Success only) set Confirmed + audit.
  * Success: payment row + Confirmed are saved together. If anything fails halfway, ALL of it is rolled back
    (no "paid but still Pending" and no "Confirmed without a payment row").
  * Fail:    the Failed payment row is saved (visible in payments, for the audit) and the booking stays
    Pending with its seats held until it expires (48 h), so the tourist can try again.
"""
import uuid

from django.db import transaction
from django.utils import timezone

from core.exceptions import ApiError

from .audit import audit
from .models import Booking, Payment
from .services import create_booking


def mock_gateway(outcome: str):
    """outcome is "pay" or "fail" (the button the user pressed). Returns (status, transaction_ref)."""
    status = Payment.SUCCESS if outcome == "pay" else Payment.FAILED
    return status, f"TX-{uuid.uuid4().hex[:10].upper()}"


def pay_booking(user, booking_id, outcome):
    with transaction.atomic():
        try:
            # Row lock: two clicks / two tabs cannot pay the same booking twice.
            booking = (Booking.objects.select_for_update(of=("self",)).select_related("departure")
                       .get(pk=booking_id, user=user))
        except Booking.DoesNotExist:
            raise ApiError("booking_not_found", "errors.booking.not_found", "Booking not found.", 404)

        now = timezone.now()
        if booking.status == Booking.CONFIRMED:
            raise ApiError("already_paid", "errors.payment.already_paid", "This booking is already paid.", 409)
        if booking.status != Booking.PENDING:
            raise ApiError("booking_not_payable", "errors.payment.not_payable",
                           "Only a Pending booking can be paid.", 409)
        if booking.expires_at is not None and booking.expires_at <= now:
            raise ApiError("booking_expired", "errors.payment.expired", "The payment time (48 hours) has run out.", 409)
        if booking.departure.start_at <= now:
            raise ApiError("departure_in_past", "errors.booking.departure_in_past",
                           "This departure has already started.", 409)

        status, ref = mock_gateway(outcome)
        payment = Payment.objects.create(
            booking=booking, amount=booking.total_cost, status=status, transaction_ref=ref,
            paid_at=now if status == Payment.SUCCESS else None)

        if status == Payment.SUCCESS:
            old = {"status": booking.status, "expires_at": booking.expires_at.isoformat() if booking.expires_at else None}
            booking.status = Booking.CONFIRMED
            booking.expires_at = None                    # nothing left to expire
            booking.save(update_fields=["status", "expires_at"])
            audit(user, "status_change", "bookings", booking.pk, old,
                  {"status": booking.status, "payment": payment.transaction_ref})
        else:
            audit(user, "payment_failed", "payments", payment.pk, None,
                  {"booking": booking.booking_ref, "transaction_ref": ref})
    return booking, payment


class _PaymentDeclined(Exception):
    """Internal signal: the gateway said Failed -> leave the transaction so everything is rolled back."""


def book_and_pay(user, departure_id, travelers_count, outcome, special_request=""):
    """
    Checkout = ONE database transaction (Task 9 transaction, rule 10):

        lock departure -> checks -> seats - n -> insert booking (Pending) -> gateway -> insert payment
        -> (Success) booking = Confirmed + audit row

    * Success: booking, seats, payment and audit are saved together (all-or-nothing).
    * Fail (or any error in any step): ROLLBACK - no booking row, no payment row, and the seats are back
      (the decrement was part of the same transaction). The tourist gets 402 `payment_failed`.
    A short audit row `checkout_rolled_back` is written AFTER the rollback so the attempt stays visible.
    """
    try:
        with transaction.atomic():
            booking = create_booking(user, departure_id, travelers_count, special_request)
            booking, payment = pay_booking(user, booking.pk, outcome)     # nested: joins this transaction
            if payment.status != Payment.SUCCESS:
                raise _PaymentDeclined()
            return booking, payment
    except _PaymentDeclined:
        audit(user, "checkout_rolled_back", "bookings", None, None,
              {"departure": departure_id, "travelers": travelers_count, "reason": "payment_failed"})
        raise ApiError("payment_failed", "errors.payment.failed_rolled_back",
                       "The payment failed. Nothing was booked and the seats are free again.", 402)
