"""Create booking status-exception demo cards for the staff review screen.

Run: python manage.py seed_review_examples
"""
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from bookings.models import AuditLog, Booking, Payment
from catalog.models import Departure


EXAMPLES = [
    ("review-demo-completed-future@example.com", "Review demo · Completed before end", Booking.COMPLETED, "[review-demo] completed_before_departure_end"),
    ("review-demo-confirmed-past@example.com", "Review demo · Confirmed after end", Booking.CONFIRMED, "[review-demo] confirmed_after_departure_end"),
    ("review-demo-pending-past@example.com", "Review demo · Pending after end", Booking.PENDING, "[review-demo] pending_after_departure_end"),
]


class Command(BaseCommand):
    help = "Create booking status-exception demo cards."

    def add_arguments(self, parser):
        parser.add_argument("--new", action="store_true", help="create another fresh set")

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Booking.objects.filter(special_request__startswith="[review-demo]")
        if existing.exists() and not options["new"]:
            self.stdout.write(self.style.WARNING(
                f"Review demo examples already exist ({existing.count()} bookings); leaving them unchanged."))
            return

        run_id = uuid.uuid4().hex[:8] if options["new"] else "initial"
        now = timezone.now()
        future_departure = (Departure.objects.select_for_update(of=("self",))
                            .filter(is_active=True, package__is_active=True, guide__is_active=True,
                                    end_at__gt=now, seats_available__gte=1)
                            .select_related("package").order_by("start_at").first())
        past_departure = (Departure.objects.select_for_update(of=("self",))
                          .filter(is_active=True, package__is_active=True, guide__is_active=True,
                                  end_at__lte=now)
                          .select_related("package").order_by("-end_at").first())
        if future_departure is None:
            raise CommandError("No future active departure for the Completed-status demo.")
        if past_departure is None:
            past_departure = Departure.objects.create(
                package=future_departure.package,
                guide=future_departure.guide,
                start_at=future_departure.start_at - timezone.timedelta(days=7),
                end_at=future_departure.end_at - timezone.timedelta(days=7),
                seats_total=future_departure.seats_total,
                seats_available=future_departure.seats_available,
                is_active=True,
            )

        created = []
        for email, full_name, status, request in EXAMPLES:
            demo_email = f"{email.split('@', 1)[0]}-{run_id}@{email.split('@', 1)[1]}" if options["new"] else email
            user = User.objects.filter(email=demo_email).first()
            if user is None:
                user = User.objects.create_user(demo_email, "Demo#Tourism2026", full_name, role=Role.TOURIST)
            elif user.role.name != Role.TOURIST:
                raise CommandError(f"{demo_email} exists but is not a tourist account.")

            departure = future_departure if status == Booking.COMPLETED else past_departure
            travel_date = timezone.localtime(departure.start_at).date()
            booking = Booking.objects.create(
                booking_ref=f"TMP-{uuid.uuid4().hex[:8]}", user=user, departure=departure,
                booking_date=travel_date - timezone.timedelta(days=1), travel_date=travel_date,
                travelers_count=1, total_cost=departure.package.base_price,
                status=status, special_request=request,
                expires_at=(now + timezone.timedelta(hours=48) if status == Booking.PENDING else None),
            )
            booking.booking_ref = f"BK-{booking.pk:04d}"
            booking.save(update_fields=["booking_ref"])
            created.append(booking)
            AuditLog.objects.create(user=None, action="seed", table_name="bookings", record_id=booking.pk,
                                    new_value={"ref": booking.booking_ref, "status": status,
                                               "reason": "status_exception_demo"})

        Payment.objects.create(
            booking=created[0], amount=created[0].total_cost, status=Payment.SUCCESS,
            transaction_ref=f"TX-EXCEPTION-{uuid.uuid4().hex[:12].upper()}", paid_at=now,
        )
        self.stdout.write(self.style.SUCCESS(
            "Created 3 booking status-exception cards: Completed-before-end, Confirmed-after-end, Pending-after-end."
        ))
        self.stdout.write("Sign in as manager@example.com or admin@example.com and open /admin/review-queue.")
