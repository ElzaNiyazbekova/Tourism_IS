"""
The role x endpoint table of Week 11 ("what each role can and cannot open") as DATA.
Used by  * accounts.tests.RolePermissionMatrixTests  (fails if a permission class is wrong)
         * `python manage.py permission_matrix`      (prints the evidence table for the report)
Owner: Amina A. (Architecture & Security)

Cell meaning: 200 = allowed and answered, 400 = allowed (the empty test body was rejected by validation, nothing is
created), 401 = not logged in, 403 = logged in but the role is not allowed. Only harmless requests are sent.
"""
from rest_framework.test import APIClient

ROLES = ["anonymous", "tourist", "guide", "analyst", "manager", "admin"]

# (label, method, url, body, expected code per role in ROLES order)
ENDPOINTS = [
    ("Public tour list",              "GET",  "/api/tours",            None, [200, 200, 200, 200, 200, 200]),
    ("My profile",                    "GET",  "/api/me",               None, [401, 200, 200, 200, 200, 200]),
    ("My bookings",                   "GET",  "/api/bookings/mine",    None, [401, 200, 403, 403, 403, 403]),
    ("Create a booking",              "POST", "/api/bookings",         {},   [401, 400, 403, 403, 403, 403]),
    ("Book + pay (checkout)",         "POST", "/api/bookings/checkout", {},  [401, 400, 403, 403, 403, 403]),
    ("Admin: tour list",              "GET",  "/api/admin/tours",      None, [401, 403, 403, 403, 200, 200]),
    ("Admin: departure list",         "GET",  "/api/admin/departures", None, [401, 403, 403, 403, 200, 200]),
    ("Admin: create tour",            "POST", "/api/admin/tours",      {},   [401, 403, 403, 403, 400, 400]),
    ("Report: counts per package",    "GET",  "/api/analytics/packages", None, [401, 403, 403, 200, 200, 200]),
]


def evaluate(users_by_role):
    """users_by_role: {"tourist": User, ...}. Returns [(label, method, url, [actual codes in ROLES order])]."""
    rows = []
    for label, method, url, body, _expected in ENDPOINTS:
        codes = []
        for role in ROLES:
            client = APIClient(HTTP_HOST="localhost")        # "testserver" is not in ALLOWED_HOSTS outside tests
            if role != "anonymous":
                client.force_authenticate(user=users_by_role[role])
            resp = client.get(url) if method == "GET" else client.post(url, body, format="json")
            codes.append(resp.status_code)
        rows.append((label, method, url, codes))
    return rows


def as_markdown(rows):
    head = "| Endpoint | " + " | ".join(ROLES) + " |\n|---|" + "---|" * len(ROLES)
    lines = [head]
    for label, method, url, codes in rows:
        lines.append(f"| {label} (`{method} {url}`) | " + " | ".join(str(c) for c in codes) + " |")
    return "\n".join(lines)
