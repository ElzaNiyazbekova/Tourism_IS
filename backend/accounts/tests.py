"""
Tests: register, login, lockout (423), two-step login (MFA), role permission matrix.
Owner: Dastan (Testing) / Amina A. (security)      Run:  python manage.py test accounts
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts import mfa
from accounts.models import User
from core import permission_matrix as pm
from core.testing import PASSWORD, client_for, make_user

LOGIN, VERIFY = "/api/auth/login", "/api/auth/mfa/verify"


def post(path, **body):
    return client_for().post(path, body, format="json")


class AuthTests(TestCase):
    def test_R1_register_creates_tourist_and_hashes_password(self):
        r = client_for().post("/api/auth/register", {"email": "New@Example.com", "password": "Better#Pass99",
                                                     "full_name": "New User"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(email="new@example.com")
        self.assertEqual(u.role.name, "tourist")
        self.assertNotIn("Better#Pass99", u.password)                    # only a hash is stored
        self.assertTrue(u.password.startswith("pbkdf2_"))
        self.assertIn("access", r.data)

    def test_R2_password_rules(self):
        for pw, code in (("12345678", "password_entirely_numeric"), ("short1", "password_too_short"),
                         ("password", "password_too_common")):
            r = client_for().post("/api/auth/register", {"email": f"{pw}@example.com", "password": pw, "full_name": "X"}, format="json")
            self.assertEqual(r.status_code, 400, pw)
            codes = [e["message_key"] for e in r.data["field_errors"]["password"]]
            self.assertIn(f"errors.field.{code}", codes, (pw, codes))

    def test_R3_duplicate_email_rejected(self):
        make_user(email="dup@example.com")
        r = client_for().post("/api/auth/register", {"email": "DUP@example.com", "password": "Better#Pass99", "full_name": "X"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["field_errors"]["email"][0]["message_key"], "errors.field.unique")

    def test_L1_login_ok_and_wrong_password(self):
        make_user(email="a@example.com")
        c = client_for()
        ok = c.post("/api/auth/login", {"email": "a@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["user"]["role"], "tourist")
        bad = c.post("/api/auth/login", {"email": "a@example.com", "password": "nope"}, format="json")
        self.assertEqual((bad.status_code, bad.data["code"]), (401, "invalid_credentials"))
        unknown = c.post("/api/auth/login", {"email": "ghost@example.com", "password": "nope"}, format="json")
        self.assertEqual((unknown.status_code, unknown.data["code"]), (401, "invalid_credentials"))   # same answer

    def test_L2_lockout_after_five_failures(self):
        u = make_user(email="lock@example.com")
        c = client_for()
        codes = [c.post("/api/auth/login", {"email": u.email, "password": "bad"}, format="json").status_code for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 401, 423])
        u.refresh_from_db()
        self.assertTrue(u.is_locked)
        self.assertEqual(c.post("/api/auth/login", {"email": u.email, "password": PASSWORD}, format="json").status_code, 423)

    def test_L3_token_gives_access_to_me(self):
        make_user(email="me@example.com", full_name="Me Myself")
        c = client_for()
        tokens = c.post("/api/auth/login", {"email": "me@example.com", "password": PASSWORD}, format="json").data
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(c.get("/api/me").data["full_name"], "Me Myself")
        self.assertEqual(client_for().get("/api/me").status_code, 401)
        patched = c.patch("/api/me", {"preferred_language": "kk"}, format="json")
        self.assertEqual(patched.data["preferred_language"], "kk")


class LockoutTests(TestCase):
    """HTTP 423: 5 wrong passwords -> locked for 15 minutes (even the right password is refused)."""

    def setUp(self):
        self.u = make_user(email="lock2@example.com")

    def fail(self, n):
        return [post(LOGIN, email=self.u.email, password="bad").status_code for _ in range(n)]

    def test_L4_423_body_header_and_duration(self):
        self.fail(4)
        r = post(LOGIN, email=self.u.email, password="bad")                    # the 5th failure
        self.assertEqual(r.status_code, 423)
        self.assertEqual((r.data["code"], r.data["message_key"]), ("account_locked", "errors.account_locked"))
        self.assertIn("locked_until", r.data)
        self.assertTrue(14 * 60 <= r.data["retry_after_seconds"] <= 15 * 60)    # 15 minutes
        self.assertEqual(r["Retry-After"], str(r.data["retry_after_seconds"]))
        self.u.refresh_from_db()
        delta = self.u.locked_until - timezone.now()
        self.assertTrue(timedelta(minutes=14, seconds=50) < delta <= timedelta(minutes=15))

    def test_L5_right_password_is_refused_while_locked_and_works_after_15_minutes(self):
        self.fail(5)
        self.assertEqual(post(LOGIN, email=self.u.email, password=PASSWORD).status_code, 423)
        User.objects.filter(pk=self.u.pk).update(locked_until=timezone.now() - timedelta(seconds=1))   # time passes
        ok = post(LOGIN, email=self.u.email, password=PASSWORD)
        self.assertEqual(ok.status_code, 200)
        self.u.refresh_from_db()
        self.assertIsNone(self.u.locked_until)

    def test_L6_unknown_email_is_never_locked_and_never_revealed(self):
        codes = [post(LOGIN, email="ghost@example.com", password="x").status_code for _ in range(8)]
        self.assertEqual(set(codes), {401})

    def test_L7_success_resets_the_counter(self):
        self.assertEqual(self.fail(3), [401, 401, 401])
        self.assertEqual(post(LOGIN, email=self.u.email, password=PASSWORD).status_code, 200)
        self.assertEqual(self.fail(4), [401, 401, 401, 401])                   # counting started again from 0
        self.u.refresh_from_db()
        self.assertFalse(self.u.is_locked)

    def test_L8_lockout_counter_survives_the_error_response(self):
        """Regression: raising inside the transaction would roll the counter back and the lock would never happen."""
        self.fail(5)
        self.u.refresh_from_db()
        self.assertTrue(self.u.is_locked)

    def test_L9_generic_423_has_the_standard_error_shape(self):
        from rest_framework.exceptions import APIException
        from core.exceptions import api_exception_handler

        class Locked(APIException):
            status_code = 423
        body = api_exception_handler(Locked(), {}).data
        self.assertEqual((body["code"], body["message_key"]), ("account_locked", "errors.account_locked"))


class MfaTests(TestCase):
    """Two-step login: password first, then the 6-digit code from the authenticator app."""

    def setUp(self):
        self.mgr = make_user("manager", email="mgr@example.com", mfa_enabled=True, mfa_secret=mfa.generate_secret())

    def step1(self):
        return post(LOGIN, email=self.mgr.email, password=PASSWORD)

    def test_M1_password_alone_gives_no_tokens(self):
        r = self.step1()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["mfa_required"])
        self.assertNotIn("access", r.data)
        self.assertNotIn("user", r.data)

    def test_M2_correct_code_logs_in(self):
        token = self.step1().data["mfa_token"]
        r = post(VERIFY, mfa_token=token, code=mfa.current_code(self.mgr))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["user"]["role"], "manager")
        c = client_for()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(c.get("/api/admin/tours").status_code, 200)

    def test_M3_the_mfa_ticket_is_not_an_access_token(self):
        token = self.step1().data["mfa_token"]
        c = client_for()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(c.get("/api/admin/tours").status_code, 401)

    def test_M4_wrong_code_401_then_five_failures_lock_423(self):
        token = self.step1().data["mfa_token"]
        codes = [post(VERIFY, mfa_token=token, code="000000").status_code for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 401, 423])
        right = post(VERIFY, mfa_token=token, code=mfa.current_code(self.mgr))
        self.assertEqual(right.status_code, 423)                                # locked: even the right code is refused
        self.assertEqual(self.step1().status_code, 423)                         # and so is the password step

    def test_M5_password_success_does_not_reset_the_code_counter(self):
        """Otherwise an attacker who knows the password could try codes forever (4 tries, log in again, 4 tries ...)."""
        for _ in range(4):
            post(VERIFY, mfa_token=self.step1().data["mfa_token"], code="000000")
        last = post(VERIFY, mfa_token=self.step1().data["mfa_token"], code="000000")
        self.assertEqual(last.status_code, 423)

    def test_M6_bad_or_expired_ticket(self):
        r = post(VERIFY, mfa_token="garbage", code="123456")
        self.assertEqual((r.status_code, r.data["code"]), (401, "mfa_token_invalid"))
        token = self.step1().data["mfa_token"]
        with override_settings(MFA_TOKEN_MAX_AGE_SECONDS=-1):                   # "5 minutes have passed"
            r = post(VERIFY, mfa_token=token, code=mfa.current_code(self.mgr))
        self.assertEqual((r.status_code, r.data["code"]), (401, "mfa_token_invalid"))

    def test_M7_staff_without_mfa_cannot_log_in(self):
        for role in ("manager", "analyst", "admin"):
            u = make_user(role)
            r = post(LOGIN, email=u.email, password=PASSWORD)
            self.assertEqual((r.status_code, r.data["code"]), (403, "mfa_setup_required"), role)
            self.assertNotIn("access", r.data)

    def test_M8_tourist_and_guide_log_in_without_mfa(self):
        for role in ("tourist", "guide"):
            self.assertEqual(post(LOGIN, email=make_user(role).email, password=PASSWORD).status_code, 200, role)

    def test_M9_code_format_and_validation(self):
        token = self.step1().data["mfa_token"]
        code = mfa.current_code(self.mgr)
        spaced = f"{code[:3]} {code[3:]}"                                        # "123 456" is accepted
        self.assertEqual(post(VERIFY, mfa_token=token, code=spaced).status_code, 200)
        self.assertEqual(post(VERIFY, mfa_token=token).status_code, 400)         # code missing
        self.assertEqual(post(VERIFY, mfa_token=token, code="abcdef").status_code, 401)

    def test_M10_wrong_password_on_an_mfa_account_still_counts(self):
        codes = [post(LOGIN, email=self.mgr.email, password="bad").status_code for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 401, 423])

    def test_M11_secret_never_leaves_the_server(self):
        token = self.step1().data["mfa_token"]
        r = post(VERIFY, mfa_token=token, code=mfa.current_code(self.mgr))
        self.assertNotIn(self.mgr.mfa_secret, r.content.decode())
        self.assertNotIn("mfa_secret", r.data["user"])


class RolePermissionMatrixTests(TestCase):
    """Week 11 table: each role and what it can / cannot open (401 = not logged in, 403 = wrong role)."""

    def test_PM1_matrix_matches_the_agreed_table(self):
        users = {r: make_user(r) for r in pm.ROLES if r != "anonymous"}
        rows = pm.evaluate(users)
        for (label, _m, _u, got), (_l, _m2, _u2, _body, expected) in zip(rows, pm.ENDPOINTS):
            self.assertEqual(got, expected, label)

    def test_PM2_analyst_is_limited_to_the_report(self):
        c = client_for(make_user("analyst"))
        self.assertEqual(c.get("/api/analytics/packages").status_code, 200)
        for url in ("/api/admin/tours", "/api/admin/departures", "/api/bookings/mine"):
            self.assertEqual(c.get(url).status_code, 403, url)
        self.assertEqual(c.post("/api/admin/tours", {}, format="json").status_code, 403)

    def test_PM3_permission_class_names_are_readable(self):
        from core import permissions as perms
        self.assertEqual(perms.IsAnalystOrStaff.__name__, "IsAnalystOrStaff")
        self.assertEqual(perms.IsManager.__name__, "IsManager")
