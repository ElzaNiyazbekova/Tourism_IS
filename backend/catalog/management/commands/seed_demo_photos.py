"""
python manage.py seed_demo_photos

Adds the bundled demo photos to an EXISTING demo database (no --reset, bookings are kept).
Packages are matched by their English demo title; a package that already has photos is skipped.
Owner: Aitore
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import PackageTranslation
from core.management.commands.seed_demo import PACKAGES, load_demo_photos


class Command(BaseCommand):
    help = "Attach the bundled photos to the demo tours that have none yet."

    @transaction.atomic
    def handle(self, *args, **opts):
        targets, skipped = [], 0
        for _d, _p, _days, _acc, _trans, _seats, texts in PACKAGES:
            tr = PackageTranslation.objects.select_related("package").filter(language_code="en", title=texts["en"][0]).first()
            if tr is None or tr.package.photos.exists():
                skipped += tr is not None
                targets.append(None)
            else:
                targets.append(tr.package)
        added = load_demo_photos(targets)
        self.stdout.write(self.style.SUCCESS(f"Added {added} photos to {sum(t is not None for t in targets)} tours "
                                             f"({skipped} already had photos)."))
