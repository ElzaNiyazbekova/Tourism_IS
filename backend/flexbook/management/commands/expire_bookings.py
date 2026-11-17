"""
python manage.py expire_bookings [--dry-run]

Plan task (Amina A.): Pending bookings unpaid for 48 hours are expired, their seats go back to the departure,
and the tourist + guide get a notification. Also closes seat-handover offers that ran out of time.
Run it every few minutes (cron / Task Scheduler); running it twice in a row is harmless.
"""
from django.core.management.base import BaseCommand

from flexbook.services import expire_overdue


class Command(BaseCommand):
    help = "Expire Pending bookings whose 48-hour payment time has run out (and stale handover offers)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")

    def handle(self, *args, **opts):
        r = expire_overdue(dry_run=opts["dry_run"])
        verb = "would expire" if opts["dry_run"] else "expired"
        self.stdout.write(f"{verb} {len(r['bookings_expired'])} booking(s)"
                          + (f": {', '.join(r['bookings_expired'])}" if r["bookings_expired"] else "")
                          + f" | seats returned: {r['seats_returned']} | handover offers closed: {r['offers_expired']}")
