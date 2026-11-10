# Week 11 (Phase 2) - Altynbek Amina: security and booking transaction
Owner: Amina A. (Architecture & Security). Everything below was executed; the outputs are real.

| Plan task | Result we show | Where in the code | How to prove it |
|---|---|---|---|
| Booking rules + seat locking | one booking succeeds, the other is rejected, seats never below 0 | `bookings/services.py` (`select_for_update`) | `python manage.py test bookings.tests.SimultaneousBookingTests` (PostgreSQL) |
| Booking transaction with ROLLBACK | a failed payment leaves no booking, seats returned | `bookings/payments.py` `book_and_pay`, `POST /api/bookings/checkout` | `python manage.py demo_rollback` and `CheckoutRollbackTests` |
| Permission classes manager / admin / analyst | table of what each role can open (401/403) | `core/permissions.py`, `core/permission_matrix.py` | `python manage.py permission_matrix` |
| MFA two-step login | a manager logs in only with the second code | `accounts/mfa.py`, `accounts/views.py` | `python manage.py test accounts.tests.MfaTests` |
| Exception 423 (account locked) | 5 wrong tries -> 15 min lock | `core/exceptions.py` `AccountLocked`, `accounts/models.py` | `python manage.py test accounts.tests.LockoutTests` |

## 1. Exception 423 - account locked
* 5 wrong passwords in a row -> `locked_until = now + 15 min`, answer **HTTP 423** `account_locked`. During the lock even the *right* password gets 423 (otherwise an attacker keeps guessing).
* Body: `{"code":"account_locked","message_key":"errors.account_locked","locked_until":"...","retry_after_seconds":899}` + header `Retry-After`. The login screen shows the message and the time when login works again.
* The same counter is used for wrong MFA codes (otherwise 1,000,000 codes could be tried).
* Unknown email: always 401, never locked (no user enumeration). A correct login resets the counter.
* Bug avoided: the counter is saved inside the transaction and the exception is raised **after** it; raising inside would roll the counter back and the lock would never happen (test `L8`).

```
$ for i in 1 2 3 4 5; do curl ... tourist2@example.com wrong password; done
try 1 -> 401   try 2 -> 401   try 3 -> 401   try 4 -> 401   try 5 -> 423
$ curl -i ... tourist2@example.com RIGHT password
HTTP/1.1 423 Locked
Retry-After: 899
{"code":"account_locked","message_key":"errors.account_locked", ... "retry_after_seconds":899}
```

## 2. Two-step login (MFA)
1. `POST /api/auth/login` password correct + MFA on -> `200 {"mfa_required": true, "mfa_token": "..."}` (no access token yet).
2. `POST /api/auth/mfa/verify {mfa_token, code}` -> `200 {access, refresh, user}`.
* `mfa_token` = signed 5-minute ticket, **not** a JWT (test `M3`: it opens nothing).
* Staff roles (manager, admin, analyst) without MFA set up cannot log in: 403 `mfa_setup_required`.
* Setup / demo: `python manage.py mfa_setup manager@example.com --show-code`. Demo accounts from `seed_demo` already have MFA, key `JBSWY3DPEHPK3PXP`.
* Known limits (say them in the defence): the secret is stored as plain text in `users.mfa_secret` (encrypt with a server key in production); a code can be reused inside its 30 s window (needs a "last used step" column); there is no recovery-code flow.

```
step 1 -> {"mfa_required":true,"mfa_token":"eyJ1aWQiOjJ9:..."}
wrong code -> 401 {"code":"invalid_mfa_code", ...}
right code -> role = manager | access token: eyJhbGciOiJIUzI1NiIsInR5c...
```

## 3. Permission classes - what each role can and cannot open
Real HTTP codes (`python manage.py permission_matrix`, demo accounts). 401 = not logged in, 403 = wrong role, 400 = allowed (the empty test body was rejected, nothing created).

| Endpoint | anonymous | tourist | guide | analyst | manager | admin |
|---|---|---|---|---|---|---|
| Public tour list (`GET /api/tours`) | 200 | 200 | 200 | 200 | 200 | 200 |
| My profile (`GET /api/me`) | 401 | 200 | 200 | 200 | 200 | 200 |
| My bookings (`GET /api/bookings/mine`) | 401 | 200 | 403 | 403 | 403 | 403 |
| Create a booking (`POST /api/bookings`) | 401 | 400 | 403 | 403 | 403 | 403 |
| Book + pay (`POST /api/bookings/checkout`) | 401 | 400 | 403 | 403 | 403 | 403 |
| Admin: tour list (`GET /api/admin/tours`) | 401 | 403 | 403 | 403 | 200 | 200 |
| Admin: departure list (`GET /api/admin/departures`) | 401 | 403 | 403 | 403 | 200 | 200 |
| Admin: create tour (`POST /api/admin/tours`) | 401 | 403 | 403 | 403 | 400 | 400 |
| Report: counts per package (`GET /api/analytics/packages`) | 401 | 403 | 403 | 200 | 200 | 200 |

Classes (`core/permissions.py`): `IsTourist`, `IsGuide`, `IsManager`, `IsAdmin`, `IsAnalyst`, `IsStaffRole` (manager+admin), `IsAnalystOrStaff`. The analyst reaches **only** the aggregate report; the report has no names, e-mails or phones (test `A2`). Angular guards are convenience only; the server decides.
`manager` and `admin` are identical today; admin-only endpoints (audit log) arrive in Phase 3 with `IsAdmin`.

## 4. Booking transaction with ROLLBACK
`book_and_pay` = ONE transaction: lock departure -> checks -> seats - n -> insert booking -> gateway -> insert payment -> Confirmed + audit.
Fail (or any crash in any step) -> everything is undone, including the seat decrement. An audit row `checkout_rolled_back` is written *after* the rollback so the attempt stays traceable.
(`POST /api/bookings/{id}/pay` from Phase 1 is unchanged: there a failed payment keeps the Pending booking for a retry within 48 h.)

```
$ python manage.py demo_rollback
BEFORE                 : bookings=0  payments=0  seats_available=5
1) press [Fail]        : HTTP 402 payment_failed
   after ROLLBACK      : bookings=0  payments=0  seats_available=5
2) crash after payment : simulated crash
   after ROLLBACK      : bookings=0  payments=0  seats_available=5
3) press [Pay]         : booking BK-0053 Confirmed, payment TX-7F1CD96C1E Success
   after COMMIT        : bookings=1  payments=1  seats_available=3
```

## 5. Seat locking test
`create_booking` locks the departure row (`SELECT ... FOR UPDATE`), so the second request waits, then sees 0 seats and gets 409 `departure_full`. The CHECK `seats_available >= 0` is the last safety net (test `S2`).
`SimultaneousBookingTests` starts real threads at the same moment (2 tourists / 1 seat, 8 tourists / 3 seats). **Needs PostgreSQL** (SQLite ignores row locks, so the test is skipped there):
```
DB_ENGINE=postgres python manage.py test bookings.tests.SimultaneousBookingTests
```
Control experiment done: with the lock removed the tests FAIL (`['ok','ok']` for one seat; 8 winners for 3 seats), with the lock they pass.

## 6. Test status
SQLite: all tests OK (2 PostgreSQL-only tests skipped). PostgreSQL 16: all tests OK, none skipped. `npm run check:i18n` -> 0 problems; `ng build` OK.
Texts to review by Amina S.: the new RU/KZ keys `auth.mfa_*`, `errors.locked_until`, `errors.mfa.*`, `errors.payment.failed_rolled_back` (first drafts).
