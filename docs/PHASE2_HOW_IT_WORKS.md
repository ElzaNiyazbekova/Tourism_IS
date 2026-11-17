# Phase 2: how it works (per member)
- **Elza (data):** `departures.is_active` + partial EXCLUDE constraint, `analyst_booking_view`, schema-agnostic `verify_constraints.sql`, regenerated `db/schema.sql`.
- **Aitore (app):** payment service (one transaction: lock booking, create payment row, confirm only on Success), pay endpoint, payment screen, admin tour/departure screens.
- **Amina A. (security/rules):** role classes (`manager/admin` for `/api/admin`, `analyst/manager/admin` for reports), tourist sees only own bookings (404 otherwise), error codes 409.
- **Amina S. (UX/i18n):** 54 new keys in EN/RU/KK (`payment.*`, `admin.*`, `errors.payment.*`).
- **Dastan (analytics/tests):** aggregate report (same numbers as the SQL view), 47 tests.

Payment flow: Pending booking -> POST `/pay` `{result}` -> `Pay`: Success payment row + booking Confirmed (hold removed); `Fail`: Failed payment row, booking stays Pending (seats held until `expires_at`).
Any internal error rolls the whole transaction back.
