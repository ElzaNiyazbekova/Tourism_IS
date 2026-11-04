# Weekly progress log  (course rule: progress must be visible and measurable)

## Week 10 - 4 Nov 2026
**Stage:** "Technical foundation exists" -> moving to "Foundation connected". **Status: AT RISK** (see cause below).
**Cause / owner / recovery:** the Django + Angular code was written in an environment where `pip`/`npm` could not be reached, so it has **not been executed yet**. Owner: Amina A. + Dastan. Recovery date: **Fri 6 Nov** - run the checklist in README ("First run") on a team machine; target status On Track.

### What changed this week (checkable)
- `db/create_tables.sql` loads cleanly on PostgreSQL 16; `db/verify_constraints.sql` -> **22 of 22 rules reject bad data** (overlap, duplicate, RESTRICT, CHECKs).
- Django project: 4 apps, 12 tables as models, auth + catalogue + first-booking endpoints (written, not yet run).
- Angular project: navbar, login/register, tour list/detail, booking panel, my bookings, EN/RU/KZ files (`npm run check:i18n` passes).
- API contract agreed: `docs/API_CONTRACT.md`.

### One measurable task per member (next 7 days)
| Member | Task | Deadline | Checkable result |
|---|---|---|---|
| Elza | Run `db/verify_constraints.sql` and `scripts/export_schema.sh`; confirm Django-created tables match `create_tables.sql` | Fri 6 Nov | `db/schema.sql` regenerated; list of any differences in the PR |
| Aitore | Register -> login -> open a tour -> book a departure in the browser | Fri 6 Nov | Row visible in `bookings` (`SELECT * FROM bookings`), screenshot of "My bookings" |
| Amina S. | Review the 104 translation keys (RU/KZ wording) and the screen list | Sun 8 Nov | Edited `public/i18n/*.json`, `check:i18n` still passes |
| Amina A. | Check lockout: 5 wrong passwords -> HTTP 423; fix any failing permission class | Fri 6 Nov | curl output pasted in `TESTS.md` |
| Dastan | Run `seed_demo`, then the Task 9 query from `db/analytics.sql` | Sat 7 Nov | Result table with 10 packages (including any with 0) |

### Final-defence answers (draft, completed in Phase 5)
Problem: double-booking of guides/seats. Who: independent tourists + local guides. Demo: see DEMO_SCRIPT (Phase 5). Inside: Django/DRF + PostgreSQL + Angular. Data flow: Angular -> /api (JWT) -> service layer (transaction + row lock) -> PostgreSQL constraints. Different: slot/seat model with DB-level protection and 3 languages incl. Kazakh.
