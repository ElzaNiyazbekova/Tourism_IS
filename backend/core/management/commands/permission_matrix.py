"""
python manage.py permission_matrix

Calls every endpoint of core/permission_matrix.py once per role (with the demo accounts from seed_demo) and prints a
Markdown table of the real HTTP codes: 401 = not logged in, 403 = wrong role. Paste it into the report.
Exit code 1 if any cell differs from the agreed table.   Owner: Amina A.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from core import permission_matrix as pm

DEMO_EMAILS = {"tourist": "tourist1@example.com", "guide": "guide1@example.com", "analyst": "analyst@example.com",
               "manager": "manager@example.com", "admin": "admin@example.com"}


class Command(BaseCommand):
    help = "Print the role x endpoint table (401/403/200) using the demo accounts."

    def handle(self, *args, **opts):
        users = {}
        for role, email in DEMO_EMAILS.items():
            users[role] = User.objects.select_related("role").filter(email=email).first()
            if users[role] is None:
                raise CommandError(f"{email} not found - run `python manage.py seed_demo` first.")
        rows = pm.evaluate(users)
        self.stdout.write(pm.as_markdown(rows))
        wrong = [(label, got, exp) for (label, _m, _u, got), (_l, _m2, _u2, _b, exp) in zip(rows, pm.ENDPOINTS) if got != exp]
        if wrong:
            for label, got, exp in wrong:
                self.stderr.write(f"MISMATCH {label}: got {got}, expected {exp}")
            raise CommandError("Permission table differs from the agreed one.")
        self.stdout.write(self.style.SUCCESS("\nAll cells match the agreed role table."))
