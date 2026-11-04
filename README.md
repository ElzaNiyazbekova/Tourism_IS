# Tourism IS - Tourism Booking & Guide Platform
Exam project, *Basics of Information Systems (INFT3107)*, KBTU - topic #30 "Plan trips and book excursions".
Stack: Django 5 + DRF + PostgreSQL 16 (SQLite fallback) - Angular (standalone, signals) - ngx-translate (EN/RU/KZ).

> **Status: Phase 1 (Week 10).** The SQL layer is verified; the Django and Angular code was written without being able to
> install packages, so **do the "First run" checklist below before anything else** and report failures in `DEFECTS.md`.

## 1. Run it (Docker - recommended)
```bash
./scripts/init_env.sh            # creates .env with random secrets (never commit .env)
docker compose up --build        # db + backend (migrate + seed) + Angular dev server
```
| What | URL |
|---|---|
| The app | http://localhost:4200 |
| API + Swagger docs (local) | http://localhost:8000/api/docs/ |
| Health | http://localhost:8000/health |

The backend container creates the migration files on first start (written into `backend/*/migrations/`) - **commit them** (`git add backend/*/migrations`).
Stop: `docker compose down` (data kept) - wipe data: `docker compose down -v`.

## 2. Run it without Docker (SQLite, no Postgres needed)
```bash
./scripts/init_env.sh && sed -i 's/^DB_ENGINE=.*/DB_ENGINE=sqlite/' .env
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python manage.py makemigrations accounts catalog bookings && python manage.py migrate
python manage.py seed_demo && python manage.py runserver          # API on :8000
cd ../frontend && npm install && npm start                          # app on :4200 (proxies /api to :8000)
```
(With a local PostgreSQL instead: keep `DB_ENGINE=postgres`, set `POSTGRES_HOST=localhost` and create the database/user from `.env`.)

## 3. Demo accounts (fictional, demo data only)
Password for **every** account: `Demo#Tourism2026` (override with `DEMO_PASSWORD` in `.env` before seeding).

| Role | Email |
|---|---|
| tourist | tourist1@example.com ... tourist5@example.com |
| guide | guide1@example.com ... guide6@example.com |
| manager | manager@example.com |
| analyst | analyst@example.com |
| admin | admin@example.com |

Reload demo data: `python manage.py seed_demo --reset` (in Docker: `docker compose exec backend python manage.py seed_demo --reset`).
Staff screens and mandatory MFA arrive in Phase 2; in Phase 1 only the tourist flow is in the UI.

## 4. First run checklist (Phase 1 acceptance - ~15 minutes)
| # | Step | Expected |
|---|---|---|
| 1 | open http://localhost:4200 | tour list with 10 tours, language buttons EN / Русский / Қазақша switch all texts |
| 2 | click a tour | departures with guide and "N seats left" |
| 3 | Sign up (new email, password `12345678`) | field error "only digits"; use a stronger password -> logged in |
| 4 | Book a departure (2 travelers) | green message "Booking BK-#### created"; seats left drops by 2 |
| 5 | "My bookings" | the booking, status Pending, "pay before" date |
| 6 | Book the same departure again | red "You already booked this departure" |
| 7 | `curl -s -XPOST localhost:8000/api/auth/login -H 'content-type: application/json' -d '{"email":"tourist1@example.com","password":"x"}'` five times | 401 four times, then **423 account_locked** |
| 8 | `psql`: `SELECT booking_ref,status,total_cost FROM bookings ORDER BY booking_id DESC LIMIT 3;` | your booking is in the database |
| 9 | on a scratch database: `createdb scratch && psql -d scratch -f db/create_tables.sql -f db/verify_constraints.sql` | 22 PASS, 0 FAIL |
| 10 | `cd frontend && npm run check:i18n` | 0 problems |

Database proof without the app (any PostgreSQL 16): `createdb scratch && psql -d scratch -f db/create_tables.sql -f db/verify_constraints.sql`.

## 5. Project map and owners
```
db/            create_tables.sql, schema.sql (export), verify_constraints.sql, analytics.sql        - Elza
backend/       config/ core/ accounts/ catalog/ bookings/ (Django apps)                              - Aitore (views) / Amina A. (security) / Elza (models)
frontend/      Angular app: src/app/{core,shared,features}, public/i18n/{en,ru,kk}.json              - Aitore / Amina S. (texts) / Amina A. (interceptor, guards)
docs/          API_CONTRACT, ER_DIAGRAM, DATA_DICTIONARY_bookings, PROGRESS, PHASE1_HOW_IT_WORKS      - Amina S. / Elza / Dastan
scripts/       init_env.sh, export_schema.sh                                                          - Amina A. / Elza
```
**Commit convention:** start every commit message with the owner tag - `[elza]`, `[aitore]`, `[amina-s]`, `[amina-a]`, `[dastan]` - so each member can prove their contribution (`git log --grep '\[aitore\]'`). Each file header also names its owner.

## 6. Security & operations notes (Task 6 decision: backup over firewall)
- Only needed ports are published; the **database has no published port**; the API is bound to localhost.
- No default passwords: all secrets come from `.env` (`.env.example` is committed, `.env` is git-ignored); the server refuses to start if a secret still says `change-me`.
- Passwords stored as PBKDF2 hashes; 8+ chars, not common, not numeric-only; lockout after 5 failures for 15 minutes.
- JWT in the `Authorization` header (no cookies), so CSRF is not exploitable; CORS allows only `CORS_ALLOWED_ORIGINS`.
- Backup/restore scripts and the test-restore procedure: Phase 5.

**Update checklist (patching routine):** 1) `pip list --outdated` / `npm outdated` monthly and before the exam week; 2) read changelogs for Django/DRF security releases; 3) bump in `requirements.txt` / `package.json`, rebuild (`docker compose build --no-cache`); 4) run tests + the First-run checklist; 5) `pip freeze > backend/requirements.lock` and commit.

## 7. Troubleshooting
| Problem | Fix |
|---|---|
| `Environment variable DJANGO_SECRET_KEY is missing or still a placeholder` | run `./scripts/init_env.sh` (or replace every `change-me...` in `.env`) |
| Backend cannot reach the database | `docker compose logs db`; with local runs set `POSTGRES_HOST=localhost` or `DB_ENGINE=sqlite` |
| `seed_demo`: "Data already exists" | use `--reset` |
| Port 4200 / 8000 busy | stop the other program or change the left side of `ports:` in `docker-compose.yml` |
| Angular: "Cannot find module ..." | `cd frontend && rm -rf node_modules && npm install` |
| Frontend shows "Could not load data" | backend not up yet: open http://localhost:8000/health |
| Migrations differ between teammates | one person generates and commits them; others `git pull` and run `migrate` only |

## 8. Known deviations (Phase 1)
Angular is pinned to 20.x (the newest version I could pin without registry access; `ng update` moves it). Chart.js / ng2-charts are added in Phase 3 with the dashboard. Destination names are English only (see Phase 1 summary, assumption 6).
# Tourism_IS
