"""
One error format for the whole API (the Angular app translates `message_key`):

    {"code": "duplicate_booking", "message_key": "errors.booking.duplicate",
     "message": "You already booked this departure.",
     "field_errors": {"email": [{"message_key": "errors.field.unique", "message": "..."}]}}

Owner: Amina A. (Architecture & Security)
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ApiError(APIException):
    """Business-rule error that carries a translatable key and optional extra data."""

    def __init__(self, code, message_key, message, status_code=status.HTTP_400_BAD_REQUEST, extra=None, field_errors=None):
        super().__init__(detail=message, code=code)
        self.status_code = status_code
        self.api_code = code
        self.message_key = message_key
        self.message = message
        self.extra = extra or {}
        self.field_errors = field_errors or {}


class AccountLocked(ApiError):
    """
    HTTP 423 Locked: the account is blocked after too many wrong passwords (or wrong MFA codes).
    Rule: LOGIN_MAX_FAILURES (5) failures -> locked for LOGIN_LOCK_MINUTES (15). Until `locked_until`
    even the CORRECT password is refused with 423 (so an attacker cannot keep guessing).
    Body: {"code": "account_locked", ..., "locked_until": ISO time, "retry_after_seconds": n}; header Retry-After: n.
    """

    def __init__(self, locked_until):
        seconds = max(1, int((locked_until - timezone.now()).total_seconds()))
        super().__init__("account_locked", "errors.account_locked", "Too many failed attempts. Try again later.",
                         status.HTTP_423_LOCKED,
                         extra={"locked_until": locked_until.isoformat(), "retry_after_seconds": seconds})


def _flatten(detail, path=""):
    """Turn DRF's nested ValidationError detail into {field: [{message_key, message}]}."""
    out = {}
    if isinstance(detail, dict):
        for key, value in detail.items():
            out.update(_flatten(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(detail, list):
        for item in detail:
            if isinstance(item, (dict, list)):
                out.update(_flatten(item, path))
            else:
                code = getattr(item, "code", "invalid")
                out.setdefault(path or "non_field_errors", []).append(
                    {"message_key": f"errors.field.{code}", "message": str(item)}
                )
    return out


_STATUS_KEYS = {
    400: ("validation_error", "errors.validation", "Please correct the highlighted fields."),
    401: ("not_authenticated", "errors.not_authenticated", "Please log in."),
    403: ("forbidden", "errors.forbidden", "You do not have permission to do this."),
    404: ("not_found", "errors.not_found", "Not found."),
    405: ("method_not_allowed", "errors.method_not_allowed", "Method not allowed."),
    423: ("account_locked", "errors.account_locked", "Too many failed attempts. Try again later."),
    429: ("throttled", "errors.throttled", "Too many requests."),
}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None  # real server bug: let Django return 500 and log it

    if isinstance(exc, ApiError):
        body = {
            "code": exc.api_code,
            "message_key": exc.message_key,
            "message": exc.message,
            "field_errors": exc.field_errors,
            **exc.extra,
        }
        response = Response(body, status=exc.status_code)
        if "retry_after_seconds" in exc.extra:           # standard HTTP hint for 423 / 429 style answers
            response["Retry-After"] = str(exc.extra["retry_after_seconds"])
        return response

    code, key, message = _STATUS_KEYS.get(response.status_code, ("error", "errors.generic", "Something went wrong."))
    field_errors = _flatten(exc.detail) if response.status_code == 400 else {}
    # An invalid/expired token is also "not authenticated" for the frontend.
    if response.status_code == 401 and isinstance(getattr(exc, "detail", None), dict) and exc.detail.get("code") == "token_not_valid":
        key = "errors.token_invalid"
    response.data = {"code": code, "message_key": key, "message": message, "field_errors": field_errors}
    return response
