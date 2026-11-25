from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command

from bookings.models import AuditLog, Booking, Payment
from core.testing import client_for, make_departure, make_user


class BookingReviewTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.admin = make_user("admin")
        self.analyst = make_user("analyst")
        self.tourist = make_user("tourist")
        self.departure = make_departure(seats=8)
        self.booking = self.make_booking(self.tourist, 2)
        self.manager_client = client_for(self.manager)

    def make_booking(self, user, travelers=1):
        now = timezone.now()
        booking = Booking.objects.create(
            booking_ref=f"TMP-{user.pk}-{Booking.objects.count() + 1}", user=user, departure=self.departure,
            booking_date=timezone.localdate(), travel_date=timezone.localtime(self.departure.start_at).date(),
            travelers_count=travelers, total_cost=Decimal("15000.00") * travelers,
            status=Booking.PENDING,
            special_request="", expires_at=now + timedelta(hours=12))
        booking.booking_ref = f"BK-{booking.pk:04d}"
        booking.save(update_fields=["booking_ref"])
        return booking

    def add_payment(self, booking, status=Payment.FAILED):
        return Payment.objects.create(booking=booking, amount=booking.total_cost, status=status,
                                      transaction_ref=f"TX-REVIEW-{booking.pk}-{Payment.objects.count()}",
                                      paid_at=timezone.now() if status == Payment.SUCCESS else None)

    def test_staff_list_is_restricted_and_contains_review_rows(self):
        url = "/api/admin/bookings/review"
        response = self.manager_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["booking_ref"], self.booking.booking_ref)
        self.assertEqual(response.data["results"][0]["customer_email"], self.tourist.email)
        self.assertEqual(client_for(self.admin).get(url).status_code, 200)
        self.assertEqual(client_for(self.analyst).get(url).status_code, 403)
        self.assertEqual(client_for().get(url).status_code, 401)

    def test_fix_uses_payment_evidence_and_audits(self):
        self.add_payment(self.booking, Payment.SUCCESS)
        response = self.manager_client.post(f"/api/admin/bookings/{self.booking.pk}/fix", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.CONFIRMED)
        self.assertIsNone(self.booking.expires_at)
        self.assertTrue(AuditLog.objects.filter(record_id=self.booking.pk, action="status_change").exists())

    def test_fix_without_successful_payment_restarts_pending_deadline(self):
        self.add_payment(self.booking)
        self.booking.expires_at = timezone.now() - timedelta(days=1)
        self.booking.save(update_fields=["expires_at"])
        response = self.manager_client.post(f"/api/admin/bookings/{self.booking.pk}/fix", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.PENDING)
        self.assertGreater(self.booking.expires_at, timezone.now())

    def test_reject_cancels_and_releases_seats(self):
        self.departure.seats_available = 5
        self.departure.save(update_fields=["seats_available"])
        response = self.manager_client.post(f"/api/admin/bookings/{self.booking.pk}/reject", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.booking.refresh_from_db()
        self.departure.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.CANCELLED)
        self.assertEqual(self.departure.seats_available, 7)

    def test_merge_combines_bookings_and_moves_payments(self):
        self.departure.seats_available = 5
        self.departure.save(update_fields=["seats_available"])
        source = self.make_booking(self.tourist, 1)
        self.add_payment(source, Payment.SUCCESS)
        response = self.manager_client.post(f"/api/admin/bookings/{source.pk}/merge",
                                            {"target_booking_id": self.booking.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.booking.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual((self.booking.travelers_count, self.booking.total_cost), (3, Decimal("45000.00")))
        self.assertEqual(self.booking.status, Booking.CONFIRMED)
        self.assertEqual(source.status, Booking.CANCELLED)
        self.assertEqual(Payment.objects.get().booking_id, self.booking.pk)
        self.assertEqual(AuditLog.objects.filter(action="booking_merge").count(), 3)

    def test_merge_rejects_different_travellers(self):
        source = self.make_booking(make_user("tourist"))
        response = self.manager_client.post(f"/api/admin/bookings/{source.pk}/merge",
                                            {"target_booking_id": self.booking.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.booking.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.PENDING)
        self.assertEqual(source.status, Booking.PENDING)

    def test_only_staff_can_change_review_bookings(self):
        url = f"/api/admin/bookings/{self.booking.pk}/reject"
        self.assertEqual(client_for(self.analyst).post(url, {}, format="json").status_code, 403)
        self.assertEqual(client_for(self.tourist).post(url, {}, format="json").status_code, 403)
        self.assertEqual(client_for(self.admin).post(url, {}, format="json").status_code, 200)


class SeedReviewExamplesCommandTests(TestCase):
    def test_new_option_adds_a_fresh_batch(self):
        make_departure(seats=20)
        call_command("seed_review_examples", stdout=StringIO())
        first_count = Booking.objects.filter(special_request__startswith="[review-demo]").count()
        call_command("seed_review_examples", "--new", stdout=StringIO())
        self.assertEqual(first_count, 5)
        self.assertEqual(Booking.objects.filter(special_request__startswith="[review-demo]").count(), 10)