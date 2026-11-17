"""
Tests: audit-log viewer.   Owner: Dastan (Testing) with Amina A.
Run:  python manage.py test bookings.test_audit
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bookings.audit import audit
from bookings.models import AuditLog
from core.testing import client_for, make_departure, make_destination, make_package, make_user

URL = "/api/admin/audit-log"


class AuditLogAccessTests(TestCase):
    def test_G1_only_admin_can_read(self):
        make_user("manager")
        for role, code in [("admin", 200), ("manager", 403), ("analyst", 403), ("tourist", 403), ("guide", 403)]:
            r = client_for(make_user(role)).get(URL)
            self.assertEqual(r.status_code, code, role)
        self.assertEqual(client_for().get(URL).status_code, 401)
        self.assertEqual(client_for().get(URL + "/facets").status_code, 401)

    def test_G2_read_only(self):
        c = client_for(make_user("admin"))
        row = AuditLog.objects.create(action="x", table_name="t")
        for call in (lambda: c.post(URL, {}, format="json"), lambda: c.patch(f"{URL}/{row.pk}", {}, format="json"),
                     lambda: c.delete(f"{URL}/{row.pk}")):
            self.assertIn(call().status_code, (404, 405))
        self.assertTrue(AuditLog.objects.filter(pk=row.pk).exists())


class AuditLogContentTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin", full_name="Ada Admin")
        self.c = client_for(self.admin)

    def test_G3_admin_actions_appear_newest_first_without_contacts(self):
        dest = make_destination()
        r = self.c.post("/api/admin/tours", {"destination": dest.pk, "base_price": "9000", "duration_days": 1,
                                             "translations": [{"language_code": "en", "title": "Audit Tour"}]}, format="json")
        tid = r.json()["id"]
        self.c.post(f"/api/admin/tours/{tid}/deactivate", {}, format="json")
        rows = self.c.get(URL, {"table": "tour_packages", "record": tid}).json()["results"]
        self.assertEqual([x["action"] for x in rows], ["deactivate", "create"])        # newest first
        self.assertEqual(rows[0]["user"]["full_name"], "Ada Admin")
        self.assertEqual(rows[0]["user"]["role"], "admin")
        self.assertEqual(rows[0]["old_value"]["is_active"], True)
        self.assertEqual(rows[0]["new_value"]["is_active"], False)
        body = self.c.get(URL).content.decode()
        self.assertNotIn(self.admin.email, body)               # no email / phone in the log screen
        self.assertNotIn("phone", body)

    def test_G4_booking_and_payment_are_logged(self):
        tourist, dep = make_user("tourist"), make_departure()
        t = client_for(tourist)
        b = t.post("/api/bookings", {"departure": dep.pk, "travelers_count": 1}, format="json").json()
        t.post(f"/api/bookings/{b['id']}/pay", {"result": "fail"}, format="json")
        t.post(f"/api/bookings/{b['id']}/pay", {"result": "pay"}, format="json")
        actions = {(x["table_name"], x["action"]) for x in self.c.get(URL).json()["results"]}
        self.assertTrue({("bookings", "create"), ("payments", "payment_failed"), ("bookings", "status_change")} <= actions)

    def test_G5_system_entries_have_no_user(self):
        audit(None, "seed", "bookings", 1, None, {"x": 1})
        row = self.c.get(URL, {"action": "seed"}).json()["results"][0]
        self.assertIsNone(row["user"])


class AuditLogFilterTests(TestCase):
    def setUp(self):
        self.admin, self.other = make_user("admin"), make_user("manager")
        self.c = client_for(self.admin)
        audit(self.admin, "create", "tour_packages", 1)
        audit(self.other, "update", "departures", 2)
        audit(self.other, "update", "tour_packages", 1)
        old = AuditLog.objects.filter(table_name="departures").first()
        AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))

    def ids(self, **q):
        return [(x["table_name"], x["action"]) for x in self.c.get(URL, q).json()["results"]]

    def test_G6_filters(self):
        self.assertEqual(len(self.ids()), 3)
        self.assertEqual(len(self.ids(table="tour_packages")), 2)
        self.assertEqual(self.ids(action="create"), [("tour_packages", "create")])
        self.assertEqual(len(self.ids(user=self.other.pk)), 2)
        self.assertEqual(len(self.ids(record=2)), 1)
        day = (timezone.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        self.assertEqual(self.ids(date_from=day, date_to=day), [("departures", "update")])
        self.assertEqual(len(self.ids(date_from=timezone.now().strftime("%Y-%m-%d"))), 2)

    def test_G7_bad_filter_values_give_400_with_field_errors(self):
        for q in ({"user": "abc"}, {"record": "x"}, {"date_from": "2026-13-45"}):
            r = self.c.get(URL, q)
            self.assertEqual(r.status_code, 400, q)
            self.assertEqual(r.json()["code"], "validation_error")
            self.assertTrue(r.json()["field_errors"])

    def test_G8_pagination_and_facets(self):
        for i in range(15):
            audit(self.admin, "update", "tour_packages", i)
        r = self.c.get(URL).json()
        self.assertEqual((len(r["results"]), r["count"]), (12, 18))
        self.assertTrue(r["next"])
        f = self.c.get(URL + "/facets").json()
        self.assertEqual(f["tables"], ["departures", "tour_packages"])
        self.assertEqual(f["actions"], ["create", "update"])
