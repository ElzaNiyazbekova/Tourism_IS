# TESTS.md (Phase 2 status; "Pass" only for what was really run)
Run: `cd backend && python manage.py test` (SQLite) or with `DB_ENGINE=postgres` (the PostgreSQL run also exercises the gist constraint).

| Result | Where | What |
|---|---|---|
| **55 tests OK** | PostgreSQL 16 | whole backend suite (incl. 8 audit-log tests G1-G8) |
| **55 tests OK** | SQLite | same suite (overlap checked in the service layer) |
| **22 PASS, 0 FAIL** | PostgreSQL 16, schema from `db/create_tables.sql` | `db/verify_constraints.sql` |
| **22 PASS, 0 FAIL** | PostgreSQL 16, schema from Django `migrate` | `db/verify_constraints.sql` |
| Pass | live API on PostgreSQL (seeded) | admin creates a tour -> in public list; deactivate -> hidden; overlap -> 409 + next slot; book -> fail (Pending, Failed row) -> pay (Confirmed, Success row) -> pay again 409; analyst 200 without personal data; tourist 403, anonymous 401 |

Audit log (G1-G8): admin-only access (manager/analyst/tourist/guide 403, anonymous 401), read-only, newest first, no email/phone, admin/booking/payment actions logged, system entries, filters, bad filter 400, pagination, facets.
Test groups: B1-B8 booking, P1-P11 payment (incl. rollback), A1-A4 analyst, C1-C2 access, T1-T6 tours, D1-D8 departures, O1 overlap, R/L accounts, H health/schema.

**Not run yet:** the Angular app (no build was possible where this was written). Manual UI checks go here after the first `npm start`:
| # | Check | Result |
|---|---|---|
| U1 | fail then pay in the browser | _to fill_ |
| U2 | admin creates a tour, it appears in `/tours` | _to fill_ |
| U3 | analyst sees only Reports | _to fill_ |
| U4 | admin: `/admin/audit` shows entries, filters work, "Details" shows before/after; manager does not see the menu item | _to fill_ |
