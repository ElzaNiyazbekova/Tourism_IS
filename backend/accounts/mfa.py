"""
Two-step login helpers (TOTP = the 6-digit code that changes every 30 seconds in Google Authenticator / Authy ...).
Owner: Amina A. (Architecture & Security)

Flow:  POST /api/auth/login (password OK, mfa_enabled)  -> 200 {"mfa_required": true, "mfa_token": "..."}
       POST /api/auth/mfa/verify {mfa_token, code}       -> 200 {access, refresh, user}
The mfa_token is a signed, 5-minute "password was correct" ticket. It is NOT a JWT: it cannot open any endpoint.
"""
import pyotp
from django.conf import settings
from django.core import signing

from core.exceptions import ApiError

_SALT = "tourism.mfa.login"


def generate_secret():
    return pyotp.random_base32()


def provisioning_uri(user):
    """otpauth:// link; shown as a QR code by a real setup screen, typed by hand in the demo."""
    return pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER)


def current_code(user):
    """Only for the demo/test commands (never exposed by the API)."""
    return pyotp.TOTP(user.mfa_secret).now()


def verify_code(user, code):
    """True if `code` is the current TOTP (one 30 s step of clock drift allowed)."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(code) != 6 or not user.mfa_secret:
        return False
    return bool(pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1))


def make_token(user):
    return signing.dumps({"uid": user.pk}, salt=_SALT)


def read_token(token):
    """Return the user id, or raise 401 mfa_token_invalid (bad signature or older than 5 minutes)."""
    try:
        return signing.loads(token, salt=_SALT, max_age=settings.MFA_TOKEN_MAX_AGE_SECONDS)["uid"]
    except (signing.BadSignature, KeyError, TypeError):      # SignatureExpired is a BadSignature
        raise ApiError("mfa_token_invalid", "errors.mfa.token_invalid",
                       "The login step expired. Enter your password again.", 401)
