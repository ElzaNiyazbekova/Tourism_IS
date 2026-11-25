"""Expire unpaid Pending bookings past 48 hours. Owner: Elza / Amina A."""
from django.core.management.base import BaseCommand

from bookings.services import expire_stale_pending


class Command(BaseCommand):
    help = "Expire unpaid Pending bookings that passed PENDING_BOOKING_HOURS"

    def handle(self, *args, **options):
        count = expire_stale_pending()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} booking(s)."))
