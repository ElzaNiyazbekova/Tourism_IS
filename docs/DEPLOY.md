# Deploy: Render (web) + Neon (PostgreSQL) - free, no card   Owner: Aitore

One web service runs everything: Django API + the built Angular app + Swagger, all on one URL
(`https://<name>.onrender.com`). Built from the root `Dockerfile`; the dev stack (`docker-compose.yml`) is unchanged.

| Piece | Where | Notes |
|---|---|---|
| Database | Neon free (0.5 GB, does not expire) | PostgreSQL 16, all constraints incl. `btree_gist` EXCLUDE work |
| Web | Render free web service (Docker) | sleeps after 15 min idle; the first request then takes ~1 min |
| Tour photos | inside the database (`stored_files`, `MEDIA_STORAGE=db`) | Render's free disk is wiped on every restart, so files are not kept on disk |

## 1. Neon (database) - ~2 min
1. Sign up at https://neon.tech (GitHub login is fine) -> **Create project**: name `tourism-is`, Postgres 16,
   region **AWS Europe Central 1 (Frankfurt)**.
2. On the project dashboard press **Connect**, switch **Connection pooling OFF**, copy the connection string
   (`postgresql://...neon.tech/neondb?sslmode=require...`). This is a secret - do not commit it or post it in chats.

## 2. Render (web service) - ~3 min + ~8 min first build
1. Sign up at https://render.com -> **New** -> **Web Service** -> **Public Git Repository**:
   `https://github.com/ElzaNiyazbekova/Tourism_IS` -> Continue.
2. Settings: Name `tourism-is` (becomes the URL), Language **Docker**, Branch `main`, Region **Frankfurt**,
   Instance type **Free**. Dockerfile path stays `./Dockerfile`.
3. **Environment variables**:

| Key | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string from step 1 |
| `DJANGO_SECRET_KEY` | press **Generate** |
| `SEED_DEMO` | `1` (loads the demo data once; skipped when data already exists) |
| `DEMO_PASSWORD` | your own password for all demo accounts (otherwise it is the public `Demo#Tourism2026` from README and anyone can log in as admin) |

4. **Advanced** -> Health Check Path: `/health`. Then **Deploy Web Service**.
5. When the log shows `Booting worker`, open `https://<name>.onrender.com`.

## Updating
A public-repo service does not redeploy by itself: after pushing to `main`, press **Manual Deploy -> Deploy latest commit**
in Render (or call the service's Deploy Hook URL from Settings). Migrations run automatically on every start.

## Reset the online demo data
Render -> service -> **Shell** is paid, so instead: set `SEED_DEMO` to `1`, and in Neon run
`DROP SCHEMA public CASCADE; CREATE SCHEMA public;` (SQL editor), then **Manual Deploy**. Everything is recreated.

## What the image does (for the defence)
`Dockerfile` stage 1 builds Angular (`ng build --configuration production`); stage 2 installs Django + gunicorn,
copies the build to `/app/frontend_dist`, runs `collectstatic`. `backend/start_prod.sh` runs `migrate`,
`seed_demo` once if `SEED_DEMO=1`, then gunicorn on `$PORT`. Django serves `/api/*`, `/static/*` (Swagger UI),
the Angular files (WhiteNoise, `WHITENOISE_ROOT`) and `index.html` for every other path (`core.views.spa_index`).
Production settings switch on by env: `DATABASE_URL`, `RENDER_EXTERNAL_HOSTNAME` (set by Render -> ALLOWED_HOSTS/CORS),
`DJANGO_DEBUG` false by default -> secure cookies + proxy HTTPS header.
