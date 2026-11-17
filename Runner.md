Docker isn't installed on your PC, and you don't need it. Your project can run with SQLite, using Python and Node. Also, `init_env.sh` is a bash script and doesn't work in PowerShell.

First, copy my updated files from `bis_project_updated.zip` into your project folder. `git pull` says "up to date" because my changes aren't in git yet.

## 1. Check that Python and Node exist
```powershell
python --version    # needs 3.11 or newer
node --version      # needs 20 or newer
```
If either is missing, install it from python.org (tick "Add to PATH") or nodejs.org, then reopen PowerShell.

## 2. Create the `.env` file (replaces init_env.sh)
Run this in `...\tourism_IS`:
```powershell
@"
DJANGO_SECRET_KEY=$(-join ((48..57)+(97..122) | Get-Random -Count 36 | ForEach-Object {[char]$_}))
DB_ENGINE=sqlite
DJANGO_DEBUG=true
"@ | Set-Content .env -Encoding ascii
```

## 3. Backend (terminal 1)
```powershell
cd backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass     # only if activation is blocked
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
The API then runs at http://localhost:8000/api/docs/. If `pip install` fails on `locust`, delete that line from `requirements.txt`, because you don't need it yet.

## 4. Frontend (terminal 2)
```powershell
cd ..\frontend
npm install
npm start
```
Open http://localhost:4200.

## 5. Log in
- **Tourist:** `tourist1@example.com` / `Demo#Tourism2026`
- **Staff (manager, analyst, admin):** the same password, plus a 6-digit code. Get it with this command in the backend terminal:
  ```powershell
  python manage.py mfa_setup manager@example.com --show-code
  ```
  Or add the key `JBSWY3DPEHPK3PXP` to an authenticator app on your phone.

## 6. Run the tests and demos
```powershell
python manage.py test
python manage.py permission_matrix
python manage.py demo_rollback
```
The concurrency tests will say "skipped" on SQLite. They need PostgreSQL.

About Docker: your repo has no `docker-compose.yml`, so `docker compose up` would fail even after installing Docker Desktop. Check with the team whether it was ever committed. For your Week 11 screenshots, the SQLite way above is enough.