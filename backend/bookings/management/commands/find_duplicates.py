"""Find and optionally repair duplicate active bookings. Owner: Elza / Amina A."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from bookings.models import AuditLog, Booking


class Command(BaseCommand):
    help = "List duplicate Pending/Confirmed/Completed pairs; use --fix to repair"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true")

    def handle(self, *args, **options):
        fix = options["fix"]
        groups = (Booking.objects.filter(status__in=[Booking.PENDING, Booking.CONFIRMED, Booking.COMPLETED])
                  .values("user_id", "departure_id").annotate(n=Count("id")).filter(n__gt=1).order_by("user_id","departure_id"))
        found = 0
        rank = {Booking.CONFIRMED: 3, Booking.COMPLETED: 2, Booking.PENDING: 1}
        for g in groups:
            rows = list(Booking.objects.filter(user_id=g["user_id"], departure_id=g["departure_id"],
                                               status__in=[Booking.PENDING,Booking.CONFIRMED,Booking.COMPLETED]).order_by("-created_at","-id"))
            rows.sort(key=lambda b:(rank.get(b.status,0), b.created_at, b.id), reverse=True)
            found += len(rows)-1
            refs = ", ".join(b.booking_ref for b in rows)
            self.stdout.write(f"user={g['user_id']} departure={g['departure_id']} count={g['n']} refs={refs}")
            if fix:
                keeper=rows[0]
                for loser in rows[1:]:
                    with transaction.atomic():
                        dep=loser.departure
                        dep.seats_available += loser.travelers_count
                        dep.save(update_fields=["seats_available"])
                        loser.status=Booking.CANCELLED
                        loser.save(update_fields=["status"])
                        AuditLog.objects.create(user=None,action="status_change",table_name="bookings",record_id=loser.id,
                                                old_value={"status":loser.status,"keeper":keeper.booking_ref},
                                                new_value={"status":Booking.CANCELLED,"reason":"find_duplicates_fix","keeper":keeper.booking_ref})
                        self.stdout.write(f"  cancelled {loser.booking_ref}; kept {keeper.booking_ref}")
        if not found:
            self.stdout.write("No duplicates found.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Found {found} duplicate(s)."))
