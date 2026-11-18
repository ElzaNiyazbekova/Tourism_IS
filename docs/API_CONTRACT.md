# API contract (agreed Week 10)  - Owner: Amina A. (architecture) with Aitore + frontend
Full machine-readable version: `/api/schema/` (OpenAPI) and Swagger UI at `/api/docs/` once the backend runs.

**Errors (always):** `{ "code", "message_key", "message", "field_errors": { field: [ {message_key, message} ] } }`
Extra keys are added per error, e.g. `next_available_departure`, `locked_until`. The frontend translates `message_key`.
**401** = not logged in, **403** = wrong role. Lists are paginated: `{count, next, previous, results}`.

## Phase 1 (implemented)
| Method + path | Who | Body / query | Success | Errors |
|---|---|---|---|---|
| GET `/health`, `/api/health` | public | - | 200 `{status, db, time}` | 503 db down |
| POST `/api/auth/register` | public | `email, password, full_name, phone?, preferred_language?` | 201 `{access, refresh, user}` | 400 field_errors (unique, password_too_short / _too_common / _entirely_numeric) |
| POST `/api/auth/login` | public | `email, password` | 200 `{access, refresh, user}` | 401 `invalid_credentials`; **423 `account_locked`** after 5 failures (15 min) |
| POST `/api/auth/refresh` | public | `refresh` | 200 `{access}` | 401 |
| GET / PATCH `/api/me` | logged in | PATCH: `full_name, phone, preferred_language` | 200 user | 401 |
| GET `/api/destinations` | public | - | page of `{id, name, country}` | - |
| GET `/api/tours` | public | `destination, price_min, price_max, date_from, date_to, guide_lang, ordering (price,-price,duration,-duration,next,rating), lang, page` | page of tour cards | 400 invalid filter |
| GET `/api/tours/{id}` | public | `lang` | tour + `departures[]` (guide, start/end, seats_available) + `reviews[]` | 404 |
| POST `/api/bookings` | tourist | `departure, travelers_count, special_request?` | 201 booking (status `Pending`, `booking_ref` `BK-####`, `total_cost` frozen) | 404 `departure_not_found`; 409 `duplicate_booking`; 409 `departure_full` / 422 `departure_in_past` (both include `next_available_departure`) |
| GET `/api/bookings/mine` | tourist | `lang, page` | page of bookings | 401 / 403 |

## Phase 2 (implemented)
| Method + path | Who | Body / query | Success | Errors |
|---|---|---|---|---|
| GET `/api/bookings/{id}` | tourist (own) | `lang` | booking + `payments[]` | 404 `booking_not_found` (also for other people's bookings) |
| POST `/api/bookings/{id}/pay` | tourist (own) | `result`: `pay` or `fail` | 200 `{result, message_key (payment.success/failed), payment, booking}`; `pay` -> booking `Confirmed`, `fail` -> stays `Pending`, payment row `Failed` | 409 `already_paid`, `booking_not_payable`, `booking_expired`, `departure_in_past`; 404 |
| GET `/api/analytics/packages` | analyst, manager, admin | `lang` | `{packages:[{package_id,title,destination,is_active,active_bookings,completed_bookings,cancelled_bookings,revenue}], totals}`. **No personal data.** | 401 / 403 |
| GET, POST `/api/admin/tours` | manager, admin | tour with `translations:[{language_code,title,description}]` (English required) | 200 page / 201 | 400 field_errors |
| GET, PATCH `/api/admin/tours/{id}` | manager, admin | same, partial; translations are upserted | 200 | 400, 404 |
| POST `/api/admin/tours/{id}/deactivate` and `/activate` | manager, admin | - | 200 tour (no DELETE endpoint: deactivate instead) | 404 |
| GET, POST `/api/admin/departures` | manager, admin | `package, guide, start_at, end_at, seats_total` | 200 page / 201 | 400; 409 `guide_overlap` (+ `next_available_departure`) |
| GET, PATCH `/api/admin/departures/{id}` | manager, admin | same, partial | 200 | 409 `departure_has_bookings` (tour/guide/time of a booked departure), 409 `guide_overlap`, 400 `seats_total` below booked |
| POST `/api/admin/departures/{id}/deactivate` / `activate` | manager, admin | - | 200 | 409 `departure_has_bookings` (deactivate), 409 `guide_overlap` (activate) |
| GET `/api/admin/destinations`, `/api/admin/guides` | manager, admin | - | plain lists for dropdowns (guides without email/phone) | 401 / 403 |
| GET `/api/admin/bookings/review` | manager, admin | `lang, page` | page of `Needs review` bookings with customer, departure and payment-attempt details | 401 / 403 |
| POST `/api/admin/bookings/{id}/fix` | manager, admin | - | resolves to `Confirmed` when a successful payment exists; otherwise `Pending` with a fresh 48-hour deadline | 404, 409 if no longer reviewable or an active duplicate exists |
| POST `/api/admin/bookings/{id}/merge` | manager, admin | `target_booking_id` | merges same-customer, same-departure review booking into target; combines travelers, frozen costs, requests and payment history | 400 invalid pair, 404, 409 capacity/conflict |
| POST `/api/admin/bookings/{id}/reject` | manager, admin | - | sets `Cancelled` and releases held seats | 404, 409 if no longer reviewable |

| GET `/api/admin/audit-log` | **admin only** | `table, action, user (id), record (id), date_from, date_to (YYYY-MM-DD), page` | page (12) of `{id, created_at, action, table_name, record_id, user:{id,full_name,role} or null, old_value, new_value}`, newest first. No email / phone. **Read-only** (no POST/PATCH/DELETE). | 400 invalid filter, 401, 403 |
| GET `/api/admin/audit-log/facets` | admin | - | `{tables:[...], actions:[...]}` for the filter dropdowns | 401 / 403 |

Every admin change, booking creation and payment result is written to `audit_log` (`user: null` = the system, e.g. seed).

## Planned (frozen names so the frontend can start)
| Phase | Endpoint |
|---|---|
| 2 | POST `/api/auth/mfa/verify` (2nd login step), MFA for staff roles (not done yet), more `/api/admin/*` (users, destinations) |
| 3 | GET `/api/search?q=&lang=` (tours, destinations, guides), GET `/api/guides/{id}`, POST `/api/bookings/{id}/cancel`, `/api/notifications`, `/api/reviews`, `/api/admin/audit-log`, guide dashboard |
