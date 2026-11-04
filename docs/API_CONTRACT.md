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

## Planned (frozen names so the frontend can start)
| Phase | Endpoint |
|---|---|
| 2 | POST `/api/auth/mfa/verify` (2nd login step), POST `/api/bookings/{id}/pay` (mock gateway: `Pay` / `Fail`), `/api/admin/*` CRUD, `/api/analytics/*` |
| 3 | GET `/api/search?q=&lang=` (tours, destinations, guides), GET `/api/guides/{id}`, POST `/api/bookings/{id}/cancel`, `/api/notifications`, `/api/reviews`, needs-review `fix/merge/reject`, `/api/admin/audit-log`, guide dashboard |
