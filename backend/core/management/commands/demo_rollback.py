"""
python manage.py demo_rollback

Live demo for the defence (Week 11: "a failed payment leaves no booking and the seats are returned").
Uses a throw-away departure + tourist, prints the numbers BEFORE and AFTER, then deletes its own test data.
  1. checkout with the "Fail" button      -> ROLLBACK: no booking, no payment, seats unchanged
  2. checkout where a step crashes after the payment row was inserted -> ROLLBACK again
  3. checkout with the "Pay" button       -> COMMIT: booking Confirmed, payment saved, seats - 2
Owner: Amina A. (Architecture & Security)
"""
from datetime import timedelta
from unittest import mock

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Guide, Role, User
from bookings.models import AuditLog, Booking, Payment
from bookings.payments import book_and_pay
from catalog.models import Departure, Destination, PackageTranslation, TourPackage
from core.exceptions import ApiError


class _Cleanup(Exception):
    pass


class Command(BaseCommand):
    help = "Show that a failed payment rolls the whole booking back (uses temporary data, leaves nothing behind)."

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():           # everything below is undone at the end, even the successful checkout
                self.run()
                raise _Cleanup()
        except _Cleanup:
            self.stdout.write(self.style.SUCCESS("\nTemporary demo data removed. Database is as before."))

    def snap(self, dep):
        dep.refresh_from_db()
        return (f"bookings={Booking.objects.filter(departure=dep).count()}  "
                f"payments={Payment.objects.filter(booking__departure=dep).count()}  seats_available={dep.seats_available}")

    def run(self):
        tourist = User.objects.create_user("rollback.demo@example.com", "Demo#Rollback2026", "Rollback Demo", role=Role.TOURIST)
        guide_user = User.objects.create_user("rollback.guide@example.com", "Demo#Rollback2026", "Rollback Guide", role=Role.GUIDE)
        guide = Guide.objects.create(user=guide_user)
        dest = Destination.objects.create(name="Demo place", country="Kazakhstan")
        pkg = TourPackage.objects.create(destination=dest, base_price=10000, duration_days=1)
        PackageTranslation.objects.create(package=pkg, language_code="en", title="Rollback demo tour", description="demo")
        start = timezone.now() + timedelta(days=400)
        dep = Departure.objects.create(package=pkg, guide=guide, start_at=start, end_at=start + timedelta(hours=4),
                                       seats_total=5, seats_available=5)

        self.stdout.write(f"BEFORE                 : {self.snap(dep)}")

        try:
            book_and_pay(tourist, dep.pk, 2, "fail")
        except ApiError as e:
            self.stdout.write(f"1) press [Fail]        : HTTP {e.status_code} {e.api_code}")
        self.stdout.write(f"   after ROLLBACK      : {self.snap(dep)}")

        with mock.patch("bookings.payments.audit", side_effect=RuntimeError("simulated crash")):
            try:
                book_and_pay(tourist, dep.pk, 2, "pay")
            except RuntimeError as e:
                self.stdout.write(f"2) crash after payment : {e}")
        self.stdout.write(f"   after ROLLBACK      : {self.snap(dep)}")

        booking, payment = book_and_pay(tourist, dep.pk, 2, "pay")
        self.stdout.write(f"3) press [Pay]         : booking {booking.booking_ref} {booking.status}, payment {payment.transaction_ref} {payment.status}")
        self.stdout.write(f"   after COMMIT        : {self.snap(dep)}")
        self.stdout.write(f"audit rows for the rolled-back attempts: {AuditLog.objects.filter(action='checkout_rolled_back').count()}")
