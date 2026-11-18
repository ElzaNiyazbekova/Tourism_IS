"""
Tests: tour photos (upload rules, order/cover, delete, public serving, demo photos).   Owner: Aitore
Run:  python manage.py test catalog
"""
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from bookings.models import AuditLog
from catalog.models import TourPhoto
from core.management.commands.seed_demo import DEMO_PHOTOS, load_demo_photos
from core.testing import client_for, make_package, make_user

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 200

_media = tempfile.mkdtemp(prefix="tour-photos-test-")


def jpeg(name="a.jpg", data=JPEG, ctype="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=ctype)


@override_settings(MEDIA_ROOT=_media)
class PhotoTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_media, ignore_errors=True)

    def setUp(self):
        self.pkg = make_package(title="Charyn Canyon Adventure")
        self.c = client_for(make_user("manager"))
        self.url = f"/api/admin/tours/{self.pkg.pk}/photos"

    def upload(self, f=None, **extra):
        return self.c.post(self.url, {"file": f or jpeg(), **extra}, format="multipart")


class PhotoAccessTests(PhotoTestBase):
    def test_P1_only_staff_can_manage(self):
        self.assertEqual(client_for().get(self.url).status_code, 401)
        for role in ("tourist", "guide", "analyst"):
            c = client_for(make_user(role))
            self.assertEqual(c.get(self.url).status_code, 403, role)
            self.assertEqual(c.post(self.url, {"file": jpeg()}, format="multipart").status_code, 403, role)
        self.assertEqual(client_for(make_user("admin")).get(self.url).status_code, 200)


class PhotoUploadTests(PhotoTestBase):
    def test_P2_upload_shows_as_cover_and_gallery_and_is_served(self):
        r = self.upload(caption="Valley of Castles", credit="Photo: Test / CC0")
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.data["id"]
        self.assertEqual(r.data["url"], f"/api/photos/{pid}")
        self.assertEqual(r.data["sort_order"], 0)

        card = [t for t in client_for().get("/api/tours").data["results"] if t["id"] == self.pkg.pk][0]
        self.assertEqual(card["cover_photo"], f"/api/photos/{pid}")
        detail = client_for().get(f"/api/tours/{self.pkg.pk}").data
        self.assertEqual(detail["photos"], [{"id": pid, "url": f"/api/photos/{pid}", "caption": "Valley of Castles",
                                             "credit": "Photo: Test / CC0"}])

        img = client_for().get(f"/api/photos/{pid}")
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img["Content-Type"], "image/jpeg")
        self.assertEqual(img["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(img.streaming_content), JPEG)
        self.assertTrue(AuditLog.objects.filter(table_name="tour_photos", action="create", record_id=pid).exists())

    def test_P3_type_is_checked_by_content_not_name(self):
        for name, data in [("evil.jpg", b"<svg onload=alert(1)>" + b" " * 50), ("x.jpg", b"MZ\x90\x00 exe"), ("a.gif", b"GIF89a....")]:
            r = self.upload(jpeg(name, data))
            self.assertEqual(r.status_code, 400, name)
            self.assertEqual(r.data["message_key"], "errors.photo.bad_type")
        self.assertEqual(self.upload(jpeg("p.png", PNG, "image/png")).status_code, 201)
        self.assertEqual(self.upload(jpeg("w.webp", WEBP, "image/webp")).status_code, 201)
        self.assertEqual(list(TourPhoto.objects.values_list("content_type", flat=True).order_by("id")), ["image/png", "image/webp"])

    def test_P4_size_count_and_missing_file(self):
        with self.settings(TOUR_PHOTO_MAX_BYTES=100):
            self.assertEqual(self.upload().data["message_key"], "errors.photo.too_large")
        self.assertEqual(self.c.post(self.url, {}, format="multipart").data["message_key"], "errors.photo.required")
        with self.settings(TOUR_PHOTO_MAX_PER_TOUR=2):
            self.assertEqual(self.upload().status_code, 201)
            self.assertEqual(self.upload().status_code, 201)
            r = self.upload()
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.data["message_key"], "errors.photo.too_many")
        self.assertEqual(TourPhoto.objects.count(), 2)

    def test_P5_stored_name_is_random_not_user_controlled(self):
        r = self.upload(jpeg("../../etc/passwd.jpg"))
        self.assertEqual(r.status_code, 201)
        name = TourPhoto.objects.get(pk=r.data["id"]).file.name
        self.assertRegex(name, r"^tour_photos/[0-9a-f]{32}\.jpg$")


class PhotoOrderDeleteTests(PhotoTestBase):
    def setUp(self):
        super().setUp()
        self.ids = [self.upload().data["id"] for _ in range(3)]

    def test_P6_reorder_changes_cover(self):
        r = self.c.post(f"{self.url}/order", {"ids": [self.ids[2], self.ids[0], self.ids[1]]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([p["id"] for p in r.data], [self.ids[2], self.ids[0], self.ids[1]])
        card = [t for t in client_for().get("/api/tours").data["results"] if t["id"] == self.pkg.pk][0]
        self.assertEqual(card["cover_photo"], f"/api/photos/{self.ids[2]}")
        self.assertTrue(AuditLog.objects.filter(table_name="tour_photos", action="reorder").exists())

    def test_P7_reorder_must_list_every_photo_once(self):
        other = make_package(title="Other")
        foreign = TourPhoto.objects.create(package=other, file="tour_photos/x.jpg", content_type="image/jpeg")
        for bad in ([self.ids[0], self.ids[1]], [self.ids[0], self.ids[0], self.ids[1]],
                    [self.ids[0], self.ids[1], foreign.pk], "1,2,3", None):
            r = self.c.post(f"{self.url}/order", {"ids": bad}, format="json")
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.data["message_key"], "errors.photo.bad_order")

    def test_P8_delete_removes_file_and_next_becomes_cover(self):
        first = TourPhoto.objects.get(pk=self.ids[0])
        path = first.file.path
        self.assertTrue(os.path.exists(path))
        with self.captureOnCommitCallbacks(execute=True):
            r = self.c.delete(f"/api/admin/photos/{self.ids[0]}")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(list(TourPhoto.objects.order_by("sort_order").values_list("id", "sort_order")),
                         [(self.ids[1], 0), (self.ids[2], 1)])
        self.assertEqual(client_for().get(f"/api/photos/{self.ids[0]}").status_code, 404)
        self.assertTrue(AuditLog.objects.filter(table_name="tour_photos", action="delete", record_id=self.ids[0]).exists())

    def test_P9_edit_caption_only(self):
        r = self.c.patch(f"/api/admin/photos/{self.ids[1]}", {"caption": "Sunset", "sort_order": 0}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p = TourPhoto.objects.get(pk=self.ids[1])
        self.assertEqual((p.caption, p.sort_order), ("Sunset", 1))      # sort_order is read-only here

    def test_P10_photo_of_inactive_tour_is_hidden(self):
        self.pkg.is_active = False
        self.pkg.save()
        self.assertEqual(client_for().get(f"/api/photos/{self.ids[0]}").status_code, 404)


@override_settings(MEDIA_ROOT=_media)
class DemoPhotoTests(TestCase):
    def test_P11_bundled_demo_photos_are_valid_and_credited(self):
        pkgs = [make_package(title=f"Demo {i}") for i in range(10)]
        self.assertEqual(load_demo_photos(pkgs), 30)
        for p in pkgs:
            photos = list(p.photos.order_by("sort_order"))
            self.assertEqual(len(photos), 3)
            for ph in photos:
                self.assertEqual(ph.content_type, "image/jpeg")
                self.assertIn("Wikimedia Commons", ph.credit)
        self.assertTrue((DEMO_PHOTOS / "credits.json").exists())

    def test_P12_migration_titles_match_seed_demo(self):
        """0004_demo_tour_photos finds tours by frozen English titles - they must stay equal to seed_demo."""
        import importlib
        from core.management.commands.seed_demo import PACKAGES
        mig = importlib.import_module("catalog.migrations.0004_demo_tour_photos")
        self.assertEqual([mig.DEMO_TITLES[str(i)] for i in range(len(PACKAGES))], [p[6]["en"][0] for p in PACKAGES])
