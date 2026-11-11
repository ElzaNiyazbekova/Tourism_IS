"""
Tests: booking, mock payment, analyst report.   Owner: Dastan (Testing) with Aitore (payment) / Amina A.
Run:  python manage.py test bookings
"""
import threading
from datetime import timedelta
from unittest import mock, skipUnless

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from bookings.models import AuditLog, Booking, Payment
from catalog.models import Departure
from core.exceptions import ApiError
from core.testing import client_for, make_departure, make_guide, make_package, make_user


def book(client, dep, travelers=2):
    return client.post("/api/bookings", {"departure": dep.pk, "travelers_count": travelers}, format="json")


class BookingCreateTests(TestCase):
    def setUp(self):
        self.tourist = make_user("tourist")
        self.dep = make_departure(seats=5)
        self.c = client_for(self.tourist)

    def test_B1_successful_booking(self):
        r = book(self.c, self.dep, 2)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["status"], "Pending")
        self.assertRegex(r.data["booking_ref"], r"^BK-\d{4}$")
        self.assertEqual(r.data["total_cost"], "30000.00")          # 15000 x 2, frozen
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.seats_available, 3)

    def test_B2_duplicate_booking_rejected(self):
        book(self.c, self.dep, 1)
        r = book(self.c, self.dep, 1)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "duplicate_booking")
        self.assertEqual(Booking.objects.count(), 1)

    def test_B4_past_departure_rejected(self):
        dep = make_departure(start_in_days=-1)
        r = book(self.c, dep, 1)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.data["code"], "departure_in_past")

    def test_B6_full_departure_rejected_with_next_slot(self):
        guide = make_guide()
        full = make_departure(guide=guide, start_in_days=5, seats=1)
        later = make_departure(guide=guide, start_in_days=20, seats=4)
        book(client_for(make_user("tourist")), full, 1)
        r = book(self.c, full, 1)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "departure_full")
        self.assertEqual(r.data["message_key"], "errors.booking.departure_full")
        self.assertEqual(r.data["next_available_departure"]["departure_id"], later.pk)

    def test_B7_inactive_departure_cannot_be_booked(self):
        dep = make_departure(active=False)
        self.assertEqual(book(self.c, dep, 1).status_code, 404)

    def test_B8_only_tourists_book(self):
        self.assertEqual(book(client_for(make_user("guide")), self.dep).status_code, 403)
        self.assertEqual(book(client_for(), self.dep).status_code, 401)


class PaymentTests(TestCase):
    def setUp(self):
        self.tourist = make_user("tourist")
        self.dep = make_departure(seats=5)
        self.c = client_for(self.tourist)
        self.booking = Booking.objects.get(pk=book(self.c, self.dep, 2).data["id"])
        self.url = f"/api/bookings/{self.booking.pk}/pay"

    def test_P1_pay_confirms_booking_and_saves_payment(self):
        r = self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["result"], "Success")
        self.assertEqual(r.data["booking"]["status"], "Confirmed")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.CONFIRMED)
        self.assertIsNone(self.booking.expires_at)
        pay = Payment.objects.get()
        self.assertEqual((pay.status, pay.amount), ("Success", self.booking.total_cost))
        self.assertTrue(pay.transaction_ref.startswith("TX-"))
        self.assertIsNotNone(pay.paid_at)
        self.assertTrue(AuditLog.objects.filter(table_name="bookings", action="status_change", record_id=self.booking.pk).exists())

    def test_P2_fail_keeps_booking_pending_and_records_failed_payment(self):
        r = self.c.post(self.url, {"result": "fail"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["result"], "Failed")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.PENDING)
        self.assertIsNotNone(self.booking.expires_at)                    # still has its 48 h
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.seats_available, 3)                    # seats still held
        pay = Payment.objects.get()
        self.assertEqual((pay.status, pay.paid_at), ("Failed", None))

    def test_P3_retry_after_fail_then_pay(self):
        self.c.post(self.url, {"result": "fail"}, format="json")
        r = self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual(r.data["booking"]["status"], "Confirmed")
        self.assertEqual(list(Payment.objects.order_by("id").values_list("status", flat=True)), ["Failed", "Success"])
        self.assertEqual(Payment.objects.values("transaction_ref").distinct().count(), 2)   # refs are unique

    def test_P4_cannot_pay_twice(self):
        self.c.post(self.url, {"result": "pay"}, format="json")
        r = self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (409, "already_paid"))
        self.assertEqual(Payment.objects.count(), 1)

    def test_P5_someone_elses_booking_is_404(self):
        r = client_for(make_user("tourist")).post(self.url, {"result": "pay"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_P6_expired_booking_cannot_be_paid(self):
        Booking.objects.filter(pk=self.booking.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        r = self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (409, "booking_expired"))
        self.assertEqual(Payment.objects.count(), 0)

    def test_P7_cancelled_booking_is_not_payable(self):
        Booking.objects.filter(pk=self.booking.pk).update(status="Cancelled")
        r = self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (409, "booking_not_payable"))

    def test_P8_invalid_result_rejected(self):
        r = self.c.post(self.url, {"result": "maybe"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("result", r.data["field_errors"])

    def test_P9_roles_enforced(self):
        self.assertEqual(client_for().post(self.url, {"result": "pay"}, format="json").status_code, 401)
        self.assertEqual(client_for(make_user("guide")).post(self.url, {"result": "pay"}, format="json").status_code, 403)

    def test_P10_rollback_when_a_step_fails(self):
        """Task 9 transaction: if confirming blows up AFTER the payment row was inserted, nothing is kept."""
        with mock.patch("bookings.payments.audit", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.c.post(self.url, {"result": "pay"}, format="json")
        self.assertEqual(Payment.objects.count(), 0)                      # payment row rolled back
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.PENDING)           # still Pending, not half-confirmed

    def test_P11_booking_detail_lists_payments(self):
        self.c.post(self.url, {"result": "fail"}, format="json")
        r = self.c.get(f"/api/bookings/{self.booking.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["status"] for p in r.data["payments"]], ["Failed"])
        self.assertEqual(client_for(make_user("tourist")).get(f"/api/bookings/{self.booking.pk}").status_code, 404)


class AnalystReportTests(TestCase):
    URL = "/api/analytics/packages"

    def setUp(self):
        self.pkg_a = make_package("Tour A", price=10000)
        self.pkg_b = make_package("Tour B", price=20000)
        self.pkg_empty = make_package("Tour Empty", price=5000)           # zero bookings on purpose
        guide = make_guide()
        dep_a = make_departure(self.pkg_a, guide, start_in_days=5, seats=9)
        dep_b = make_departure(self.pkg_b, guide, start_in_days=15, seats=9)
        t1, t2, t3 = (make_user("tourist", phone="+7 701 999 88 77") for _ in range(3))
        # A: two active (one paid), B: one cancelled
        self.b1 = Booking.objects.get(pk=book(client_for(t1), dep_a, 2).data["id"])
        client_for(t1).post(f"/api/bookings/{self.b1.pk}/pay", {"result": "pay"}, format="json")
        book(client_for(t2), dep_a, 1)
        b3 = book(client_for(t3), dep_b, 1).data["id"]
        Booking.objects.filter(pk=b3).update(status="Cancelled")
        self.analyst = make_user("analyst")

    def rows(self, r):
        return {row["title"]: row for row in r.data["packages"]}

    def test_A1_analyst_sees_counts_per_package(self):
        r = client_for(self.analyst).get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        rows = self.rows(r)
        self.assertEqual(rows["Tour A"]["active_bookings"], 2)
        self.assertEqual(rows["Tour A"]["revenue"], "20000.00")            # only the paid booking (2 x 10000)
        self.assertEqual(rows["Tour B"]["active_bookings"], 0)
        self.assertEqual(rows["Tour B"]["cancelled_bookings"], 1)
        self.assertEqual(rows["Tour Empty"]["active_bookings"], 0)         # zero-booking package still listed
        self.assertEqual(r.data["totals"]["active_bookings"], 2)

    def test_A2_no_personal_data_in_the_report(self):
        r = client_for(self.analyst).get(self.URL)
        allowed = {"package_id", "title", "destination", "is_active", "active_bookings", "completed_bookings",
                   "cancelled_bookings", "revenue"}
        for row in r.data["packages"]:
            self.assertEqual(set(row), allowed)
        text = r.content.decode().lower()
        for secret in ("@example.com", "phone", "+7 701", "email", "full_name"):
            self.assertNotIn(secret, text)

    def test_A3_other_roles_and_anonymous(self):
        self.assertEqual(client_for().get(self.URL).status_code, 401)
        for role in ("tourist", "guide"):
            self.assertEqual(client_for(make_user(role)).get(self.URL).status_code, 403, role)
        for role in ("manager", "admin"):
            self.assertEqual(client_for(make_user(role)).get(self.URL).status_code, 200, role)

    def test_A4_analyst_cannot_use_staff_endpoints(self):
        c = client_for(self.analyst)
        for url in ("/api/admin/tours", "/api/admin/departures", "/api/admin/guides", "/api/admin/destinations"):
            self.assertEqual(c.get(url).status_code, 403, url)
        self.assertEqual(c.get("/api/bookings/mine").status_code, 403)


def checkout(client, dep, result, travelers=2):
    return client.post("/api/bookings/checkout", {"departure": dep.pk, "travelers_count": travelers, "result": result}, format="json")


class CheckoutRollbackTests(TestCase):
    """Task 9 transaction: booking + seats + payment are ONE unit. A failed payment rolls everything back."""

    def setUp(self):
        self.tourist = make_user("tourist")
        self.dep = make_departure(seats=5)
        self.c = client_for(self.tourist)

    def state(self):
        self.dep.refresh_from_db()
        return Booking.objects.count(), Payment.objects.count(), self.dep.seats_available

    def test_K1_pay_saves_booking_seats_and_payment_together(self):
        r = checkout(self.c, self.dep, "pay")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["booking"]["status"], "Confirmed")
        self.assertEqual(self.state(), (1, 1, 3))
        self.assertEqual(Payment.objects.get().status, "Success")

    def test_K2_failed_payment_leaves_no_booking_and_seats_are_returned(self):
        r = checkout(self.c, self.dep, "fail")
        self.assertEqual((r.status_code, r.data["code"]), (402, "payment_failed"))
        self.assertEqual(r.data["message_key"], "errors.payment.failed_rolled_back")
        self.assertEqual(self.state(), (0, 0, 5))                                # nothing saved, all 5 seats free
        self.assertFalse(AuditLog.objects.filter(table_name="bookings", action="create").exists())
        self.assertTrue(AuditLog.objects.filter(action="checkout_rolled_back").exists())   # the attempt is still traceable

    def test_K3_crash_after_the_payment_row_was_inserted_rolls_everything_back(self):
        with mock.patch("bookings.payments.audit", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                checkout(self.c, self.dep, "pay")
        self.assertEqual(self.state(), (0, 0, 5))

    def test_K4_not_enough_seats_changes_nothing(self):
        r = checkout(self.c, self.dep, "pay", travelers=6)
        self.assertEqual((r.status_code, r.data["code"]), (409, "departure_full"))
        self.assertEqual(self.state(), (0, 0, 5))

    def test_K5_try_again_after_a_failed_payment(self):
        checkout(self.c, self.dep, "fail")
        r = checkout(self.c, self.dep, "pay")                                    # no "duplicate booking": the first was rolled back
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.state(), (1, 1, 3))

    def test_K6_roles_and_validation(self):
        self.assertEqual(checkout(client_for(), self.dep, "pay").status_code, 401)
        self.assertEqual(checkout(client_for(make_user("guide")), self.dep, "pay").status_code, 403)
        bad = self.c.post("/api/bookings/checkout", {"departure": self.dep.pk, "travelers_count": 1, "result": "maybe"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.state(), (0, 0, 5))


class SeatLockingTests(TestCase):
    """Booking rule: the last seat can be sold only once; seats never go below 0."""

    def test_S1_second_tourist_is_rejected_when_the_last_seat_is_taken(self):
        dep = make_departure(seats=1)
        first = book(client_for(make_user("tourist")), dep, 1)
        second = book(client_for(make_user("tourist")), dep, 1)
        self.assertEqual(first.status_code, 201)
        self.assertEqual((second.status_code, second.data["code"]), (409, "departure_full"))
        dep.refresh_from_db()
        self.assertEqual(dep.seats_available, 0)
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 1)

    def test_S2_database_check_is_the_last_safety_net(self):
        """Even if the Python check were skipped, the CHECK (seats_available >= 0) refuses a negative number."""
        dep = make_departure(seats=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Departure.objects.filter(pk=dep.pk).update(seats_available=-1)
        dep.refresh_from_db()
        self.assertEqual(dep.seats_available, 1)


class LastSeatRaceTests(TransactionTestCase):
    """Real race for the final seat. This test must run on PostgreSQL because SQLite ignores row locks.

    Use PostgreSQL for the real run:
        docker compose up -d db
        docker compose run --rm backend python manage.py test bookings.tests.LastSeatRaceTests -v 2
    """

    def _race(self, n_users):
        dep = make_departure(seats=1)
        users = [make_user("tourist") for _ in range(n_users)]
        barrier = threading.Barrier(n_users)
        codes = []

        def worker(user):
            try:
                barrier.wait()
                response = client_for(user).post(
                    "/api/bookings",
                    {"departure": dep.pk, "travelers_count": 1},
                    format="json",
                )
                codes.append(response.status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(user,)) for user in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        dep.refresh_from_db()
        return dep, codes

    def test_R1_two_tourists_last_seat(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Race test needs PostgreSQL row locking")

        dep, codes = self._race(2)
        self.assertEqual(sorted(codes), [201, 409])
        dep.refresh_from_db()
        self.assertEqual(dep.seats_available, 0)
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 1)

    def test_R2_five_tourists_last_seat(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Race test needs PostgreSQL row locking")

        dep, codes = self._race(5)
        self.assertEqual(codes.count(201), 1)
        self.assertEqual(codes.count(409), 4)
        dep.refresh_from_db()
        self.assertEqual(dep.seats_available, 0)
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 1)

    def test_R3_seats_never_negative(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Race test needs PostgreSQL row locking")

        dep = make_departure(seats=2)
        users = [make_user("tourist") for _ in range(3)]
        barrier = threading.Barrier(3)
        codes = []

        def worker(user):
            try:
                barrier.wait()
                response = client_for(user).post(
                    "/api/bookings",
                    {"departure": dep.pk, "travelers_count": 1},
                    format="json",
                )
                codes.append(response.status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(user,)) for user in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        dep.refresh_from_db()
        self.assertEqual(codes.count(201), 2)
        self.assertEqual(codes.count(409), 1)
        self.assertEqual(dep.seats_available, 0)
        self.assertGreaterEqual(dep.seats_available, 0)
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 2)


@skipUnless(connection.vendor == "postgresql", "row locks (SELECT ... FOR UPDATE) need PostgreSQL; SQLite ignores them")
class SimultaneousBookingTests(TransactionTestCase):
    """
    Real parallel requests. Run on PostgreSQL:  DB_ENGINE=postgres python manage.py test bookings.tests.SimultaneousBookingTests
    The threads all start at the same moment (Barrier); the row lock in create_booking lets one in at a time.
    """

    def race(self, seats, workers):
        from bookings.services import create_booking
        dep = make_departure(seats=seats)
        tourists = [make_user("tourist") for _ in range(workers)]
        barrier, results = threading.Barrier(workers), []

        def worker(user):
            try:
                barrier.wait()
                create_booking(user, dep.pk, 1)
                results.append("ok")
            except ApiError as e:
                results.append(e.api_code)
            finally:
                connection.close()                                               # each thread has its own connection

        threads = [threading.Thread(target=worker, args=(u,)) for u in tourists]
        [t.start() for t in threads]
        [t.join() for t in threads]
        dep.refresh_from_db()
        return dep, results

    def test_S3_two_tourists_one_seat_exactly_one_wins(self):
        dep, results = self.race(seats=1, workers=2)
        self.assertEqual(sorted(results), ["departure_full", "ok"])
        self.assertEqual(dep.seats_available, 0)                                 # never below 0
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 1)

    def test_S4_eight_tourists_three_seats_exactly_three_win(self):
        dep, results = self.race(seats=3, workers=8)
        self.assertEqual(results.count("ok"), 3)
        self.assertEqual(results.count("departure_full"), 5)
        self.assertEqual(dep.seats_available, 0)
        self.assertEqual(Booking.objects.filter(departure=dep).count(), 3)
