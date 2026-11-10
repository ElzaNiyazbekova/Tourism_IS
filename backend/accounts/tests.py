"""
Tests: register, login, lockout, role permission classes (Phase 1 behaviour, now really executed).
Owner: Dastan (Testing) / Amina A. (security)      Run:  python manage.py test accounts
"""
from django.test import TestCase

from accounts.models import User
from core.testing import PASSWORD, client_for, make_user


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
