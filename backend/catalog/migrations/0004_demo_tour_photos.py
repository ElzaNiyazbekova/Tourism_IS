"""
Data migration: attach the bundled demo photos (catalog/demo_photos) to the demo tours of an EXISTING database,
so teammates only need `git pull` + `python manage.py migrate` to see them.   Owner: Aitore

- Matches tours by their English demo title (frozen below, so later edits to seed_demo cannot break it).
- Skips a tour that already has photos -> safe to run on any database; a fresh/empty database is a no-op
  (seed_demo adds the photos itself when it creates the tours).
- Reverse: does nothing (photos added later by staff must never be removed by a rollback).
"""
import json
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations

DEMO_PHOTOS = Path(__file__).resolve().parents[1] / "demo_photos"

# index in demo_photos/credits.json -> English demo title (from seed_demo, Nov 2026)
DEMO_TITLES = {
    "0": "Almaty City Highlights",
    "1": "Kok-Tobe and Medeu Day",
    "2": "Charyn Canyon Adventure",
    "3": "Big Almaty Lake Hike",
    "4": "Astana Modern Architecture Walk",
    "5": "Turkistan Heritage Tour",
    "6": "Mangystau: Valley of Balls",
    "7": "Bozzhyra Tract Expedition",
    "8": "Burabay Lakes and Rocks",
    "9": "Burabay Sunrise Trek",
}


def add_demo_photos(apps, schema_editor):
    credits_file = DEMO_PHOTOS / "credits.json"
    if not credits_file.exists():
        return
    PackageTranslation = apps.get_model("catalog", "PackageTranslation")
    TourPhoto = apps.get_model("catalog", "TourPhoto")
    credits = json.loads(credits_file.read_text(encoding="utf-8"))
    added = 0
    for idx, title in DEMO_TITLES.items():
        tr = PackageTranslation.objects.filter(language_code="en", title=title).select_related("package").first()
        if tr is None or TourPhoto.objects.filter(package=tr.package).exists():
            continue
        for order, item in enumerate(credits.get(idx, [])):
            src = DEMO_PHOTOS / item["file"]
            if not src.exists():
                continue
            name = default_storage.save(f"tour_photos/{uuid.uuid4().hex}.jpg", ContentFile(src.read_bytes()))
            TourPhoto.objects.create(package=tr.package, file=name, content_type="image/jpeg", sort_order=order,
                                     credit=f"Photo: {item['author']} / {item['license']} / Wikimedia Commons")
            added += 1
    if added:
        print(f"\n  Added {added} demo tour photos.")


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_tour_photos"),
    ]

    operations = [
        migrations.RunPython(add_demo_photos, migrations.RunPython.noop),
    ]
