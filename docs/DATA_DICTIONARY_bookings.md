# Data dictionary - `bookings` (Task 7 style)   Owner: Elza

| Field | Meaning | Format / example | Required / rule |
|---|---|---|---|
| booking_id | Internal row number | INT, 17 | Auto-generated primary key |
| booking_ref | Number shown to the tourist | `BK-0017` | **System-generated only**; unique; never typed by a user |
| user_id | Who booked (a tourist) | INT, FK -> users | Required; user must exist; RESTRICT on delete |
| departure_id | Which slot (package + guide + time) | INT, FK -> departures | Required; departure must exist and not be in the past; RESTRICT on delete |
| booking_date | Day the booking was made | `2026-11-04` | Required; set by the system |
| travel_date | Day of the tour | `2026-11-21` | Required; **>= booking_date**; taken from the departure |
| travelers_count | Number of people | INT, 2 | Required; **> 0**; <= seats_available |
| total_cost | Price in KZT, frozen | DECIMAL(10,2), `30000.00` | Required; **>= 0**; = base_price x travelers_count at booking time, never recalculated |
| status | Lifecycle state | `Pending` / `Confirmed` / `Cancelled` / `Completed` / `Needs review` | Required; only these 5 values; changed only by the system or a manager; `Completed` only on/after the departure date |
| special_request | Free text from the tourist | `Vegetarian lunch` | Optional; <= 500 characters |
| created_at | Row creation time | `2026-11-04 18:02+05` | Set by the system |
| expires_at | Deadline to pay | `2026-11-06 18:02+05` | Pending only: created_at + 48 h; then auto-Cancelled and the seat released |

**Extra rules** - one *active* (Pending/Confirmed) booking per tourist per departure (partial UNIQUE index); every status change is written to `audit_log`.
