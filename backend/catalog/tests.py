"""
Tests: staff CRUD for tours and departures, public list, overlap rule.   Owner: Dastan (Testing) / Aitore
Run:  python manage.py test catalog
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bookings.models import AuditLog, Booking
from catalog.models import Departure, TourPackage
from catalog.services import assert_no_guide_overlap
from core.exceptions import ApiError
from core.testing import client_for, make_departure, make_destination, make_guide, make_package, make_user


def tour_payload(dest, **over):
    body = {"destination": dest.pk, "base_price": "25000.00", "duration_days": 2,
            "accommodation_included": True, "transport_included": False,
            "translations": [{"language_code": "en", "title": "Admin Made Tour", "description": "Created in admin"},
                             {"language_code": "ru", "title": "Тур из админки", "description": "Создан в админке"},
                             {"language_code": "kk", "title": "Әкімшіден тур", "description": "Әкімші жасады"}]}
    body.update(over)
    return body


class AdminAccessTests(TestCase):
    URLS = ["/api/admin/tours", "/api/admin/departures", "/api/admin/destinations", "/api/admin/guides"]

    def test_C1_roles(self):
        for url in self.URLS:
            self.assertEqual(client_for().get(url).status_code, 401, url)
            for role in ("tourist", "guide", "analyst"):
                self.assertEqual(client_for(make_user(role)).get(url).status_code, 403, (url, role))
            for role in ("manager", "admin"):
                self.assertEqual(client_for(make_user(role)).get(url).status_code, 200, (url, role))

    def test_C2_lookup_lists_have_no_contact_data(self):
        make_guide()
        text = client_for(make_user("manager")).get("/api/admin/guides").content.decode().lower()
        for secret in ("@example.com", "phone", "+7 700", "email"):
            self.assertNotIn(secret, text)


class AdminTourTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.c = client_for(self.manager)
        self.dest = make_destination()

    def test_T1_create_tour_appears_in_public_list(self):
        r = self.c.post("/api/admin/tours", tour_payload(self.dest), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["is_active"])
        tid = r.data["id"]
        pub = client_for().get("/api/tours?lang=ru")                         # anonymous visitor, Russian UI
        self.assertEqual(pub.status_code, 200)
        self.assertIn(tid, [t["id"] for t in pub.data["results"]])
        self.assertEqual([t["title"] for t in pub.data["results"] if t["id"] == tid], ["Тур из админки"])
        self.assertTrue(AuditLog.objects.filter(table_name="tour_packages", action="create", record_id=tid,
                                                user=self.manager).exists())

    def test_T2_validation(self):
        bad = self.c.post("/api/admin/tours", tour_payload(self.dest, base_price="-5", duration_days=0), format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("base_price", bad.data["field_errors"])
        self.assertIn("duration_days", bad.data["field_errors"])
        no_en = tour_payload(self.dest, translations=[{"language_code": "ru", "title": "Только RU"}])
        r = self.c.post("/api/admin/tours", no_en, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("translations", r.data["field_errors"])
        self.assertEqual(TourPackage.objects.count(), 0)                     # nothing half-saved

    def test_T3_edit_tour_changes_public_view(self):
        tid = self.c.post("/api/admin/tours", tour_payload(self.dest), format="json").data["id"]
        r = self.c.patch(f"/api/admin/tours/{tid}", {"base_price": "30000.00",
                         "translations": [{"language_code": "en", "title": "Renamed Tour", "description": "x"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        pub = client_for().get(f"/api/tours/{tid}").data
        self.assertEqual((pub["title"], pub["base_price"]), ("Renamed Tour", "30000.00"))
        self.assertTrue(AuditLog.objects.filter(table_name="tour_packages", action="update", record_id=tid).exists())

    def test_T4_deactivate_hides_from_public_and_activate_restores(self):
        tid = self.c.post("/api/admin/tours", tour_payload(self.dest), format="json").data["id"]
        r = self.c.post(f"/api/admin/tours/{tid}/deactivate")
        self.assertEqual((r.status_code, r.data["is_active"]), (200, False))
        self.assertNotIn(tid, [t["id"] for t in client_for().get("/api/tours").data["results"]])
        self.assertEqual(client_for().get(f"/api/tours/{tid}").status_code, 404)
        self.assertTrue(TourPackage.objects.filter(pk=tid).exists())          # deactivated, NOT deleted
        self.c.post(f"/api/admin/tours/{tid}/activate")
        self.assertIn(tid, [t["id"] for t in client_for().get("/api/tours").data["results"]])
        self.assertEqual(AuditLog.objects.filter(table_name="tour_packages", record_id=tid,
                                                 action__in=["deactivate", "activate"]).count(), 2)

    def test_T5_no_delete(self):
        pkg = make_package()
        self.assertEqual(self.c.delete(f"/api/admin/tours/{pkg.pk}").status_code, 405)

    def test_T6_is_active_cannot_be_set_by_edit(self):
        pkg = make_package()
        self.c.patch(f"/api/admin/tours/{pkg.pk}", {"is_active": False}, format="json")
        pkg.refresh_from_db()
        self.assertTrue(pkg.is_active)                                       # only the audited action can change it


class AdminDepartureTests(TestCase):
    def setUp(self):
        self.c = client_for(make_user("admin"))
        self.pkg = make_package()
        self.guide = make_guide()

    def payload(self, days=10, hours=8, **over):
        start = (timezone.now() + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
        body = {"package": self.pkg.pk, "guide": self.guide.pk, "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=hours)).isoformat(), "seats_total": 6}
        body.update(over)
        return body

    def test_D1_create_departure_is_empty_and_public(self):
        r = self.c.post("/api/admin/departures", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["seats_total"], r.data["seats_available"]), (6, 6))
        pub = client_for().get(f"/api/tours/{self.pkg.pk}").data
        self.assertEqual([d["id"] for d in pub["departures"]], [r.data["id"]])

    def test_D2_overlap_same_guide_rejected_with_next_slot(self):
        make_departure(self.pkg, self.guide, start_in_days=30)
        first = self.c.post("/api/admin/departures", self.payload(days=10, hours=8), format="json").data["id"]
        r = self.c.post("/api/admin/departures", self.payload(days=10, hours=4), format="json")   # same start -> overlaps
        self.assertEqual((r.status_code, r.data["code"]), (409, "guide_overlap"))
        # the guide's next free slot is the earliest one that still has seats: the departure created first
        self.assertEqual(r.data["next_available_departure"]["departure_id"], first)
        self.assertEqual(Departure.objects.filter(guide=self.guide, package=self.pkg).count(), 2)   # nothing saved

    def test_D3_back_to_back_is_allowed(self):
        first = self.payload(days=10, hours=8)
        self.c.post("/api/admin/departures", first, format="json")
        start2 = first["end_at"]                                              # starts exactly when the first ends
        r = self.c.post("/api/admin/departures", self.payload(days=10, hours=3, start_at=start2,
                        end_at=(timezone.now() + timedelta(days=11)).isoformat()), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_D4_validation(self):
        past = self.c.post("/api/admin/departures", self.payload(days=-2), format="json")
        self.assertEqual(past.status_code, 400)
        self.assertIn("start_at", past.data["field_errors"])
        bad_end = self.payload()
        bad_end["end_at"] = bad_end["start_at"]
        self.assertIn("end_at", self.c.post("/api/admin/departures", bad_end, format="json").data["field_errors"])
        self.assertIn("seats_total", self.c.post("/api/admin/departures", self.payload(seats_total=0), format="json").data["field_errors"])
        self.guide.is_active = False
        self.guide.save()
        self.assertIn("guide", self.c.post("/api/admin/departures", self.payload(), format="json").data["field_errors"])

    def test_D5_edit_seats_cannot_go_below_booked(self):
        dep = make_departure(self.pkg, self.guide, seats=5)
        client_for(make_user("tourist")).post("/api/bookings", {"departure": dep.pk, "travelers_count": 3}, format="json")
        bad = self.c.patch(f"/api/admin/departures/{dep.pk}", {"seats_total": 2}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.c.patch(f"/api/admin/departures/{dep.pk}", {"seats_total": 8}, format="json")
        self.assertEqual((ok.status_code, ok.data["seats_total"], ok.data["seats_available"]), (200, 8, 5))

    def test_D6_cannot_move_a_departure_with_bookings(self):
        dep = make_departure(self.pkg, self.guide)
        client_for(make_user("tourist")).post("/api/bookings", {"departure": dep.pk, "travelers_count": 1}, format="json")
        new_start = (dep.start_at + timedelta(days=1)).isoformat()
        r = self.c.patch(f"/api/admin/departures/{dep.pk}", {"start_at": new_start, "end_at": (dep.end_at + timedelta(days=1)).isoformat()}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (409, "departure_has_bookings"))

    def test_D7_deactivate_departure(self):
        dep = make_departure(self.pkg, self.guide)
        r = self.c.post(f"/api/admin/departures/{dep.pk}/deactivate")
        self.assertEqual((r.status_code, r.data["is_active"]), (200, False))
        self.assertEqual(client_for().get(f"/api/tours/{self.pkg.pk}").data["departures"], [])      # hidden from tourists
        self.assertEqual(client_for(make_user("tourist")).post("/api/bookings", {"departure": dep.pk, "travelers_count": 1},
                                                              format="json").status_code, 404)    # cannot be booked
        self.assertTrue(Departure.objects.filter(pk=dep.pk).exists())
        # the guide's time is free again: another departure in the same hours is now allowed
        again = self.c.post("/api/admin/departures", {"package": self.pkg.pk, "guide": self.guide.pk,
                            "start_at": dep.start_at.isoformat(), "end_at": dep.end_at.isoformat(), "seats_total": 3}, format="json")
        self.assertEqual(again.status_code, 201, again.content)
        # ... and now the old one can NOT be switched back on (it would overlap)
        self.assertEqual(self.c.post(f"/api/admin/departures/{dep.pk}/activate").data["code"], "guide_overlap")

    def test_D8_cannot_deactivate_departure_with_active_booking(self):
        dep = make_departure(self.pkg, self.guide)
        client_for(make_user("tourist")).post("/api/bookings", {"departure": dep.pk, "travelers_count": 1}, format="json")
        r = self.c.post(f"/api/admin/departures/{dep.pk}/deactivate")
        self.assertEqual((r.status_code, r.data["code"]), (409, "departure_has_bookings"))
        dep.refresh_from_db()
        self.assertTrue(dep.is_active)
        Booking.objects.update(status="Cancelled")
        self.assertEqual(self.c.post(f"/api/admin/departures/{dep.pk}/deactivate").status_code, 200)


class OverlapServiceTests(TestCase):
    """BR-01 for the SQLite fallback: the service layer enforces what PostgreSQL's EXCLUDE constraint does."""

    def test_O1_overlap_detected_and_adjacent_allowed(self):
        guide = make_guide()
        dep = make_departure(guide=guide, start_in_days=10, hours=8)
        with self.assertRaises(ApiError) as ctx:
            assert_no_guide_overlap(guide.pk, dep.start_at + timedelta(hours=2), dep.end_at + timedelta(hours=2))
        self.assertEqual(ctx.exception.api_code, "guide_overlap")
        assert_no_guide_overlap(guide.pk, dep.end_at, dep.end_at + timedelta(hours=2))        # no error
        assert_no_guide_overlap(make_guide().pk, dep.start_at, dep.end_at)                    # another guide: fine
