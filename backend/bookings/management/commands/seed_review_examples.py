"""Create working Needs review examples for the staff review screen.

Run: python manage.py seed_review_examples
Safe to run more than once: existing example rows are preserved.
"""
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from bookings.models import AuditLog, Booking, Payment
from catalog.models import Departure


EXAMPLES = [
    ("review-demo-fix-pending@example.com", "Review demo · Fix pending", "[review-demo] FIX: no successful payment; Fix returns Pending."),
    ("review-demo-fix-confirmed@example.com", "Review demo · Fix confirmed", "[review-demo] FIX: successful payment; Fix confirms the booking."),
    ("review-demo-merge@example.com", "Review demo · Merge", "[review-demo] MERGE: source booking; merge this with its matching booking."),
    ("review-demo-merge@example.com", "Review demo · Merge", "[review-demo] MERGE: target booking; select the other matching booking."),
    ("review-demo-reject@example.com", "Review demo · Reject", "[review-demo] REJECT: use Reject to cancel and release the held seat."),
]


class Command(BaseCommand):
    help = "Create review-queue demo bookings for Fix, Merge, and Reject actions."

    def add_arguments(self, parser):
        parser.add_argument("--new", action="store_true", help="create another fresh set even if examples already exist")

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Booking.objects.filter(special_request__startswith="[review-demo]")
        if existing.exists() and not options["new"]:
            self.stdout.write(self.style.WARNING(
                f"Review demo examples already exist ({existing.count()} bookings); leaving them unchanged."))
            return

        run_id = uuid.uuid4().hex[:8] if options["new"] else "initial"
        example_rows = [
            (f"{email.split('@', 1)[0]}-{run_id}@{email.split('@', 1)[1]}", full_name, request)
            if options["new"] else (email, full_name, request)
            for email, full_name, request in EXAMPLES
        ]
        now = timezone.now()
        departure = (Departure.objects.select_for_update(of=("self",))
                     .filter(is_active=True, package__is_active=True, guide__is_active=True,
                             start_at__gt=now, seats_available__gte=len(EXAMPLES))
                     .select_related("package").order_by("-seats_available", "start_at").first())
        if departure is None:
            raise CommandError("No future active departure has enough free seats for the review examples.")

        demo_users = {}
        for email, full_name, _ in example_rows:
            if email not in demo_users:
                user = User.objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(email, "Demo#Tourism2026", full_name, role=Role.TOURIST)
                elif user.role.name != Role.TOURIST:
                    raise CommandError(f"{email} exists but is not a tourist account.")
                demo_users[email] = user

        bookings = []
        for email, _, request in example_rows:
            booking = Booking.objects.create(
                booking_ref=f"TMP-{uuid.uuid4().hex[:8]}", user=demo_users[email], departure=departure,
                booking_date=timezone.localdate(), travel_date=timezone.localtime(departure.start_at).date(),
                travelers_count=1, total_cost=departure.package.base_price,
                status=Booking.NEEDS_REVIEW, special_request=request,
            )
            booking.booking_ref = f"BK-{booking.pk:04d}"
            booking.save(update_fields=["booking_ref"])
            bookings.append(booking)
            AuditLog.objects.create(user=None, action="seed", table_name="bookings", record_id=booking.pk,
                                    new_value={"ref": booking.booking_ref, "status": booking.status,
                                               "reason": "review_demo"})

        # All examples reserve one seat so Reject and Merge exercise real seat accounting.
        departure.seats_available -= len(bookings)
        departure.save(update_fields=["seats_available"])

        payment_examples = [
            (bookings[0], Payment.FAILED),
            (bookings[1], Payment.SUCCESS),
            (bookings[2], Payment.FAILED),
            (bookings[3], Payment.SUCCESS),
        ]
        for booking, status in payment_examples:
            Payment.objects.create(booking=booking, amount=booking.total_cost, status=status,
                                   transaction_ref=f"TX-REVIEW-{uuid.uuid4().hex[:12].upper()}",
                                   paid_at=now if status == Payment.SUCCESS else None)

        self.stdout.write(self.style.SUCCESS(
            "Created 5 review cards: Fix → Pending, Fix → Confirmed, a matching Merge pair, and Reject."
        ))
        if options["new"]:
            self.stdout.write(f"This fresh example batch is tagged {run_id} in its demo customer emails.")
        self.stdout.write("Sign in as manager@example.com or admin@example.com and open /admin/bookings-review.")
