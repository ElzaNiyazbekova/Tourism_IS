"""
Guide cabinet: own profile, own departures, travellers list, access rules.   Owner: Aitore
Run:  python manage.py test catalog.test_guide_cabinet
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bookings.models import AuditLog, Booking
from bookings.services import create_booking
from catalog.models import Departure
from core.testing import client_for, make_departure, make_guide, make_package, make_user


class GuideCabinetTests(TestCase):
    def setUp(self):
        self.guide = make_guide("en,ru")
        self.other = make_guide("kk")
        self.pkg = make_package("Almaty City Tour")
        self.soon = make_departure(self.pkg, guide=self.guide, start_in_days=5, seats=6)
        self.later = make_departure(self.pkg, guide=self.guide, start_in_days=30)
        self.foreign = make_departure(self.pkg, guide=self.other, start_in_days=6)
        self.past = make_departure(self.pkg, guide=self.guide, start_in_days=12)
        Departure.objects.filter(pk=self.past.pk).update(start_at=timezone.now() - timedelta(days=3),
                                                         end_at=timezone.now() - timedelta(days=3) + timedelta(hours=8))
        self.tourist = make_user("tourist", phone="+7 700 000 0001")
        create_booking(self.tourist, self.soon.pk, 3, "vegetarian lunch")
        cancelled = create_booking(make_user("tourist"), self.soon.pk, 2)
        Booking.objects.filter(pk=cancelled.pk).update(status=Booking.CANCELLED)
        self.c = client_for(self.guide.user)

    def test_GC1_only_guides(self):
        for url in ("/api/guide/me", "/api/guide/departures", f"/api/guide/departures/{self.soon.pk}"):
            self.assertEqual(client_for().get(url).status_code, 401, url)
            for role in ("tourist", "manager", "admin", "analyst"):
                self.assertEqual(client_for(make_user(role)).get(url).status_code, 403, (url, role))

    def test_GC2_me_with_stats(self):
        r = self.c.get("/api/guide/me")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["languages"], ["en", "ru"])
        self.assertEqual((r.data["upcoming_count"], r.data["completed_count"], r.data["travelers_upcoming"]), (2, 1, 3))

    def test_GC3_edit_profile_is_validated_and_audited(self):
        r = self.c.patch("/api/guide/me", {"bio": "  Mountain guide  ", "languages": ["ru", "kk", "ru"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.guide.refresh_from_db()
        self.assertEqual((self.guide.bio, self.guide.languages_spoken), ("Mountain guide", "kk,ru"))
        self.assertTrue(AuditLog.objects.filter(table_name="guides", action="update", record_id=self.guide.pk).exists())
        for bad in ({"languages": []}, {"languages": ["de"]}, {"bio": "x" * 2001}):
            self.assertEqual(self.c.patch("/api/guide/me", bad, format="json").status_code, 400, bad)
        r = self.c.patch("/api/guide/me", {"is_active": False}, format="json")   # read-only field is ignored
        self.guide.refresh_from_db()
        self.assertTrue(self.guide.is_active)

    def test_GC4_own_departures_upcoming_and_past(self):
        up = self.c.get("/api/guide/departures").data["results"]
        self.assertEqual([d["id"] for d in up], [self.soon.pk, self.later.pk])      # soonest first, no foreign ones
        self.assertEqual((up[0]["bookings_count"], up[0]["travelers_count"]), (1, 3))   # cancelled booking not counted
        past = self.c.get("/api/guide/departures?when=past").data["results"]
        self.assertEqual([d["id"] for d in past], [self.past.pk])
        self.assertEqual(self.c.get("/api/guide/departures?when=tomorrow").status_code, 400)

    def test_GC5_travellers_of_own_departure_only(self):
        r = self.c.get(f"/api/guide/departures/{self.soon.pk}")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data["travelers"]), 1)
        t = r.data["travelers"][0]
        self.assertEqual((t["phone"], t["travelers_count"], t["special_request"]), ("+7 700 000 0001", 3, "vegetarian lunch"))
        self.assertNotIn("total_cost", t)
        self.assertEqual(self.c.get(f"/api/guide/departures/{self.foreign.pk}").status_code, 404)
