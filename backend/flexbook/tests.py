"""
Tests for FlexBook.   Owner: Amina A.  (run:  python manage.py test flexbook)

C  cancellation + preview        E  expire_bookings job        U  undo cancel
H  seat handover                 T  timeline                   A  tamper-evident audit chain
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from bookings.audit import audit
from bookings.models import AuditLog, Booking, Notification
from core.testing import client_for, make_departure, make_guide, make_user
from flexbook.models import AuditSeal, SeatTransfer
from flexbook.sealing import seal_missing, verify_chain
from flexbook.services import expire_overdue


def book(client, dep, n=2):
    r = client.post("/api/bookings", {"departure": dep.pk, "travelers_count": n}, format="json")
    assert r.status_code == 201, r.content
    return Booking.objects.get(pk=r.data["id"])


def pay(client, b):
    r = client.post(f"/api/bookings/{b.pk}/pay", {"result": "pay"}, format="json")
    assert r.status_code == 200, r.content
    b.refresh_from_db()


class Base(TestCase):
    def setUp(self):
        self.tourist = make_user("tourist")
        self.c = client_for(self.tourist)
        self.dep = make_departure(start_in_days=10, seats=5)


class CancelTests(Base):
    def test_C1_cancel_pending_returns_seats_and_audits(self):
        b = book(self.c, self.dep, 2)
        r = self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["booking"]["status"], "Cancelled")
        self.assertIn("undo_until", r.data)
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.seats_available, 5)
        row = AuditLog.objects.filter(action="cancel", record_id=b.pk).get()
        self.assertEqual(row.user, self.tourist)
        self.assertEqual(row.old_value["status"], "Pending")

    def test_C2_cancel_confirmed_booking(self):
        b = book(self.c, self.dep, 1)
        pay(self.c, b)
        self.assertEqual(self.c.post(f"/api/bookings/{b.pk}/cancel").status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, "Cancelled")

    def test_C3_exactly_at_3_days_is_allowed_but_inside_is_not(self):
        ok = book(self.c, make_departure(start_in_days=3, seats=5), 1)
        # start_in_days=3 truncates minutes, so the start is slightly under 3 days away: move it safely beyond
        ok.departure.start_at = timezone.now() + timedelta(days=3, minutes=5)
        ok.departure.end_at = ok.departure.start_at + timedelta(hours=8)
        ok.departure.save()
        self.assertEqual(self.c.post(f"/api/bookings/{ok.pk}/cancel").status_code, 200)

        late = book(self.c, make_departure(start_in_days=2, seats=5), 1)
        r = self.c.post(f"/api/bookings/{late.pk}/cancel")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "cancel_too_late")
        self.assertEqual(r.data["message_key"], "errors.cancel.too_late")
        self.assertTrue(r.data["handover_available"])
        late.refresh_from_db()
        self.assertEqual(late.status, "Pending")               # nothing changed

    def test_C4_cannot_cancel_twice(self):
        b = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        r = self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "not_cancellable")
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.seats_available, 5)           # seats returned once only

    def test_C5_someone_elses_booking_is_404_and_roles_are_enforced(self):
        b = book(self.c, self.dep, 1)
        self.assertEqual(client_for(make_user("tourist")).post(f"/api/bookings/{b.pk}/cancel").status_code, 404)
        self.assertEqual(client_for(make_user("admin")).post(f"/api/bookings/{b.pk}/cancel").status_code, 403)
        self.assertEqual(client_for().post(f"/api/bookings/{b.pk}/cancel").status_code, 401)

    def test_C6_notifications_for_tourist_and_guide(self):
        b = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertTrue(Notification.objects.filter(user=self.tourist, message_key="notifications.cancelled").exists())
        self.assertTrue(Notification.objects.filter(user=self.dep.guide.user, message_key="notifications.guide_cancelled").exists())

    def test_C7_preview_changes_nothing(self):
        b = book(self.c, self.dep, 2)
        r = self.c.get(f"/api/bookings/{b.pk}/cancel-preview")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["allowed"])
        self.assertEqual(r.data["seats_returned"], 2)
        b.refresh_from_db()
        self.assertEqual(b.status, "Pending")
        late = book(self.c, make_departure(start_in_days=1, seats=5), 1)
        p = self.c.get(f"/api/bookings/{late.pk}/cancel-preview").data
        self.assertFalse(p["allowed"])
        self.assertEqual(p["reason_key"], "errors.cancel.too_late")
        self.assertTrue(p["handover_possible"])

    def test_C8_freed_seats_can_be_booked_again(self):
        full = make_departure(seats=1)
        b = book(self.c, full, 1)
        other = client_for(make_user("tourist"))
        self.assertEqual(other.post("/api/bookings", {"departure": full.pk, "travelers_count": 1}, format="json").status_code, 409)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(other.post("/api/bookings", {"departure": full.pk, "travelers_count": 1}, format="json").status_code, 201)


class ExpireTests(Base):
    def _old(self, b, hours_ago=1):
        Booking.objects.filter(pk=b.pk).update(expires_at=timezone.now() - timedelta(hours=hours_ago))

    def test_E1_expired_pending_is_cancelled_and_seats_return(self):
        b = book(self.c, self.dep, 3)
        self._old(b)
        out = StringIO()
        call_command("expire_bookings", stdout=out)
        b.refresh_from_db()
        self.dep.refresh_from_db()
        self.assertEqual(b.status, "Cancelled")
        self.assertEqual(self.dep.seats_available, 5)
        self.assertIn(b.booking_ref, out.getvalue())
        row = AuditLog.objects.get(action="expire", record_id=b.pk)
        self.assertIsNone(row.user)                              # done by the system
        self.assertEqual(row.new_value["reason"], "unpaid_48h")
        self.assertTrue(Notification.objects.filter(user=self.tourist, message_key="notifications.expired").exists())
        self.assertTrue(Notification.objects.filter(user=self.dep.guide.user, message_key="notifications.guide_expired").exists())

    def test_E2_fresh_paid_and_cancelled_bookings_are_untouched(self):
        fresh = book(self.c, self.dep, 1)
        paid = book(self.c, make_departure(seats=5), 1)
        pay(self.c, paid)
        self._old(paid)                                          # even with an old timestamp a paid booking has none
        r = expire_overdue()
        self.assertEqual(r["bookings_expired"], [])
        fresh.refresh_from_db(); paid.refresh_from_db()
        self.assertEqual((fresh.status, paid.status), ("Pending", "Confirmed"))

    def test_E3_running_twice_is_harmless(self):
        b = book(self.c, self.dep, 2)
        self._old(b)
        self.assertEqual(len(expire_overdue()["bookings_expired"]), 1)
        self.assertEqual(expire_overdue()["bookings_expired"], [])
        self.dep.refresh_from_db()
        self.assertEqual(self.dep.seats_available, 5)            # returned once, not twice

    def test_E4_dry_run_changes_nothing(self):
        b = book(self.c, self.dep, 2)
        self._old(b)
        r = expire_overdue(dry_run=True)
        self.assertEqual(r["bookings_expired"], [b.booking_ref])
        b.refresh_from_db()
        self.assertEqual(b.status, "Pending")
        self.assertFalse(AuditLog.objects.filter(action="expire").exists())

    def test_E5_expired_booking_can_no_longer_be_paid(self):
        b = book(self.c, self.dep, 1)
        self._old(b)
        expire_overdue()
        r = self.c.post(f"/api/bookings/{b.pk}/pay", {"result": "pay"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_E6_expiry_is_not_undoable(self):
        b = book(self.c, self.dep, 1)
        self._old(b)
        expire_overdue()
        self.assertEqual(self.c.post(f"/api/bookings/{b.pk}/undo-cancel").status_code, 409)

    def test_E7_stale_handover_offers_are_closed(self):
        b = book(self.c, self.dep, 1)
        t = SeatTransfer.objects.create(booking=b, from_user=self.tourist, to_email="x@example.com",
                                        expires_at=timezone.now() - timedelta(minutes=1))
        r = expire_overdue()
        t.refresh_from_db()
        self.assertEqual((r["offers_expired"], t.status), (1, "expired"))


class UndoTests(Base):
    def test_U1_undo_restores_pending_booking_and_seats(self):
        b = book(self.c, self.dep, 2)
        old_exp = Booking.objects.get(pk=b.pk).expires_at
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        r = self.c.post(f"/api/bookings/{b.pk}/undo-cancel")
        self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db(); self.dep.refresh_from_db()
        self.assertEqual(b.status, "Pending")
        self.assertEqual(b.expires_at, old_exp)                  # the 48 h clock is NOT reset
        self.assertEqual(self.dep.seats_available, 3)
        self.assertTrue(AuditLog.objects.filter(action="cancel_undo", record_id=b.pk).exists())

    def test_U2_undo_restores_confirmed(self):
        b = book(self.c, self.dep, 1)
        pay(self.c, b)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(self.c.post(f"/api/bookings/{b.pk}/undo-cancel").status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, "Confirmed")

    def test_U3_window_closes(self):
        b = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        row = AuditLog.objects.get(action="cancel", record_id=b.pk)
        row.new_value = {**row.new_value, "undo_until": (timezone.now() - timedelta(seconds=1)).isoformat()}
        AuditLog.objects.filter(pk=row.pk).update(new_value=row.new_value)
        r = self.c.post(f"/api/bookings/{b.pk}/undo-cancel")
        self.assertEqual((r.status_code, r.data["code"]), (409, "undo_window_closed"))

    def test_U4_seats_taken_meanwhile_rejects_with_next_slot(self):
        guide = make_guide()
        dep = make_departure(guide=guide, start_in_days=10, seats=1)
        later = make_departure(guide=guide, start_in_days=30, seats=3)
        b = book(self.c, dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        client_for(make_user("tourist")).post("/api/bookings", {"departure": dep.pk, "travelers_count": 1}, format="json")
        r = self.c.post(f"/api/bookings/{b.pk}/undo-cancel")
        self.assertEqual((r.status_code, r.data["code"]), (409, "departure_full"))
        self.assertEqual(r.data["next_available_departure"]["departure_id"], later.pk)
        b.refresh_from_db()
        self.assertEqual(b.status, "Cancelled")

    def test_U5_cannot_undo_when_not_cancelled_or_when_not_yours(self):
        b = book(self.c, self.dep, 1)
        self.assertEqual(self.c.post(f"/api/bookings/{b.pk}/undo-cancel").status_code, 409)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(client_for(make_user("tourist")).post(f"/api/bookings/{b.pk}/undo-cancel").status_code, 404)

    def test_U6_cannot_undo_into_a_duplicate_booking(self):
        b = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        book(self.c, self.dep, 1)                                # book the same departure again
        r = self.c.post(f"/api/bookings/{b.pk}/undo-cancel")
        self.assertEqual((r.status_code, r.data["code"]), (409, "duplicate_booking"))

    def test_U7_flex_state_reports_undo_and_cancel_rules(self):
        near = book(self.c, make_departure(start_in_days=1, seats=5), 1)
        far = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{far.pk}/cancel")
        state = {s["booking_id"]: s for s in self.c.get("/api/bookings/flex-state").data}
        self.assertFalse(state[near.pk]["can_cancel"])
        self.assertTrue(state[near.pk]["can_handover"])
        self.assertTrue(state[far.pk]["can_undo"])
        self.assertFalse(state[far.pk]["can_handover"])


class HandoverTests(Base):
    def setUp(self):
        super().setUp()
        self.friend = make_user("tourist", email="friend@example.com", full_name="Friend One")
        self.fc = client_for(self.friend)
        self.b = book(self.c, self.dep, 2)

    def offer(self, email="friend@example.com", b=None):
        return self.c.post(f"/api/bookings/{(b or self.b).pk}/handover", {"email": email, "message": "enjoy"}, format="json")

    def test_H1_full_happy_path(self):
        r = self.offer()
        self.assertEqual(r.status_code, 201, r.content)
        inc = self.fc.get("/api/handovers/incoming").data
        self.assertEqual(len(inc), 1)
        self.assertEqual((inc[0]["from_name"], inc[0]["booking_ref"], inc[0]["travelers_count"]), (self.tourist.full_name, self.b.booking_ref, 2))
        self.assertNotIn("email", " ".join(inc[0].keys()))      # sender's contact data never leaves
        acc = self.fc.post(f"/api/handovers/{inc[0]['id']}/accept")
        self.assertEqual(acc.status_code, 200, acc.content)
        self.b.refresh_from_db(); self.dep.refresh_from_db()
        self.assertEqual(self.b.user, self.friend)
        self.assertEqual(self.dep.seats_available, 3)            # seats unchanged: same seats, new owner
        self.assertEqual(self.b.total_cost, 2 * self.dep.package.base_price)
        self.assertTrue(AuditLog.objects.filter(action="handover", record_id=self.b.pk).exists())
        self.assertEqual(self.c.get(f"/api/bookings/{self.b.pk}/cancel-preview").status_code, 404)   # no longer mine

    def test_H2_works_inside_the_3_day_lock_window(self):
        late = book(self.c, make_departure(start_in_days=1, seats=5), 1)
        self.assertEqual(self.c.post(f"/api/bookings/{late.pk}/cancel").status_code, 409)
        self.assertEqual(self.offer(b=late).status_code, 201)

    def test_H3_same_answer_for_unknown_email(self):
        known, unknown = self.offer(), None
        self.c.post(f"/api/handovers/{known.data['id']}/withdraw")
        unknown = self.offer("nobody@example.com")
        self.assertEqual(unknown.status_code, 201)
        self.assertEqual(set(known.data), set(unknown.data))

    def test_H4_validation_and_single_open_offer(self):
        self.assertEqual(self.offer(self.tourist.email).status_code, 400)
        self.assertEqual(self.c.post(f"/api/bookings/{self.b.pk}/handover", {"email": "nope"}, format="json").status_code, 400)
        self.assertEqual(self.offer().status_code, 201)
        self.assertEqual(self.offer("other@example.com").status_code, 409)

    def test_H5_only_the_addressee_can_accept_or_decline(self):
        t = self.offer().data["id"]
        stranger = client_for(make_user("tourist"))
        self.assertEqual(stranger.post(f"/api/handovers/{t}/accept").status_code, 404)
        self.assertEqual(stranger.post(f"/api/handovers/{t}/decline").status_code, 404)
        self.assertEqual(self.c.post(f"/api/handovers/{t}/accept").status_code, 404)    # not even the sender
        self.assertEqual(client_for(make_user("guide")).post(f"/api/handovers/{t}/accept").status_code, 403)

    def test_H6_decline_and_withdraw(self):
        t = self.offer().data["id"]
        self.assertEqual(self.fc.post(f"/api/handovers/{t}/decline").status_code, 200)
        self.assertEqual(self.fc.post(f"/api/handovers/{t}/accept").status_code, 409)
        t2 = self.offer().data["id"]
        self.assertEqual(self.c.post(f"/api/handovers/{t2}/withdraw").status_code, 200)
        self.assertEqual(self.fc.get("/api/handovers/incoming").data, [])
        self.b.refresh_from_db()
        self.assertEqual(self.b.user, self.tourist)

    def test_H7_cancelling_withdraws_open_offer(self):
        t = self.offer().data["id"]
        self.c.post(f"/api/bookings/{self.b.pk}/cancel")
        self.assertEqual(SeatTransfer.objects.get(pk=t).status, "withdrawn")
        self.assertEqual(self.fc.post(f"/api/handovers/{t}/accept").status_code, 409)

    def test_H8_offer_expires(self):
        t = self.offer().data["id"]
        SeatTransfer.objects.filter(pk=t).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.fc.get("/api/handovers/incoming").data, [])
        self.assertEqual(self.fc.post(f"/api/handovers/{t}/accept").status_code, 409)

    def test_H9_receiver_with_own_booking_on_same_departure_is_refused(self):
        book(self.fc, self.dep, 1)
        t = self.offer().data["id"]
        r = self.fc.post(f"/api/handovers/{t}/accept")
        self.assertEqual((r.status_code, r.data["code"]), (409, "duplicate_booking"))
        self.b.refresh_from_db()
        self.assertEqual(self.b.user, self.tourist)

    def test_H10_pending_offer_never_outlives_the_payment_deadline(self):
        t = SeatTransfer.objects.get(pk=self.offer().data["id"])
        self.assertLessEqual(t.expires_at, Booking.objects.get(pk=self.b.pk).expires_at)

    def test_H11_receiver_gets_a_notification_only_if_account_exists(self):
        self.offer()
        self.assertTrue(Notification.objects.filter(user=self.friend, message_key="notifications.handover_offer").exists())


class TimelineTests(Base):
    def test_T1_story_in_order_without_other_peoples_names(self):
        b = book(self.c, self.dep, 1)
        self.c.post(f"/api/bookings/{b.pk}/pay", {"result": "fail"}, format="json")
        self.c.post(f"/api/bookings/{b.pk}/pay", {"result": "pay"}, format="json")
        self.c.post(f"/api/bookings/{b.pk}/cancel")
        r = self.c.get(f"/api/bookings/{b.pk}/timeline")
        self.assertEqual(r.status_code, 200)
        kinds = [e["kind"] for e in r.data["events"]]
        self.assertEqual(kinds, ["created", "payment_failed", "confirmed", "cancelled"])
        self.assertTrue(all(e["by"] == "you" for e in r.data["events"]))
        self.assertNotIn(self.tourist.email, str(r.data))

    def test_T2_only_the_owner_sees_it(self):
        b = book(self.c, self.dep, 1)
        self.assertEqual(client_for(make_user("tourist")).get(f"/api/bookings/{b.pk}/timeline").status_code, 404)
        self.assertEqual(client_for().get(f"/api/bookings/{b.pk}/timeline").status_code, 401)

    def test_T3_system_expiry_is_labelled_system(self):
        b = book(self.c, self.dep, 1)
        Booking.objects.filter(pk=b.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        expire_overdue()
        ev = self.c.get(f"/api/bookings/{b.pk}/timeline").data["events"][-1]
        self.assertEqual((ev["kind"], ev["by"]), ("expired", "system"))


class AuditChainTests(TestCase):
    def setUp(self):
        self.admin = client_for(make_user("admin"))
        for i in range(4):
            audit(None, "update", "tours", i + 1, {"price": i}, {"price": i + 1})

    def test_A1_every_new_row_is_sealed_and_chain_is_intact(self):
        self.assertEqual(AuditSeal.objects.count(), AuditLog.objects.count())
        r = verify_chain()
        self.assertEqual(r["status"], "intact")
        self.assertIsNotNone(r["head_hash"])

    def test_A2_editing_a_row_is_detected_at_that_row(self):
        victim = AuditLog.objects.order_by("id")[1]
        AuditLog.objects.filter(pk=victim.pk).update(new_value={"price": 999})     # bypasses the app, like raw SQL
        r = verify_chain()
        self.assertEqual(r["status"], "broken")
        self.assertEqual(r["first_break"], {"audit_id": victim.pk, "reason": "row_modified"})

    def test_A3_deleting_a_row_from_the_middle_is_detected(self):
        victim = AuditLog.objects.order_by("id")[1]
        AuditLog.objects.filter(pk=victim.pk).delete()                              # cascades its seal too
        r = verify_chain()
        self.assertEqual(r["status"], "broken")
        self.assertEqual(r["first_break"]["reason"], "chain_link")

    def test_A4_rows_inserted_behind_the_apps_back_are_flagged_then_backfilled(self):
        AuditLog.objects.bulk_create([AuditLog(action="sneaky", table_name="x", record_id=1)])   # bulk_create sends no signal
        self.assertEqual(verify_chain()["status"], "incomplete")
        self.assertEqual(seal_missing(), 1)
        self.assertEqual(verify_chain()["status"], "intact")

    def test_A5_endpoint_is_admin_only_and_read_only(self):
        self.assertEqual(self.admin.get("/api/admin/audit-log/integrity").data["status"], "intact")
        for role in ("tourist", "manager", "analyst", "guide"):
            self.assertEqual(client_for(make_user(role)).get("/api/admin/audit-log/integrity").status_code, 403, role)
        self.assertEqual(client_for().get("/api/admin/audit-log/integrity").status_code, 401)
        self.assertEqual(self.admin.post("/api/admin/audit-log/integrity").status_code, 405)

    def test_A6_real_booking_actions_are_chained_too(self):
        t = make_user("tourist"); c = client_for(t)
        b = book(c, make_departure(), 1)
        c.post(f"/api/bookings/{b.pk}/cancel")
        self.assertEqual(verify_chain()["status"], "intact")
        self.assertEqual(AuditSeal.objects.count(), AuditLog.objects.count())

    def test_A7_command_exit_code_on_tamper(self):
        from django.core.management.base import CommandError
        out = StringIO()
        call_command("seal_audit_log", "--verify", stdout=out)
        self.assertIn("status=intact", out.getvalue())
        AuditLog.objects.filter(pk=AuditLog.objects.first().pk).update(action="forged")
        with self.assertRaises(CommandError):
            call_command("seal_audit_log", "--verify", stdout=StringIO())
