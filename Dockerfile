# Production image for Render (one service: Django API + the built Angular app).   Owner: Aitore
# The dev stack (docker-compose.yml, backend/Dockerfile, frontend/Dockerfile) is unchanged.

# ---- 1. build Angular ----------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx ng build --configuration production

# ---- 2. Django + gunicorn ------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend_dist MEDIA_STORAGE=db
WORKDIR /app
COPY backend/requirements.txt .
RUN grep -v '^locust' requirements.txt > req.txt && pip install --no-cache-dir -r req.txt && rm req.txt
COPY backend/ ./
COPY --from=frontend /fe/dist/tourism-is/browser /app/frontend_dist
# static files of Swagger UI / DRF; dummy secret only for this build step (the real one comes from Render)
RUN DJANGO_SECRET_KEY=build-only-not-secret DB_ENGINE=sqlite python manage.py collectstatic --noinput -v0 \
 && rm -rf .venv media demo.sqlite3 && chmod +x start_prod.sh \
 && useradd --create-home app && chown -R app /app
USER app
EXPOSE 10000
CMD ["./start_prod.sh"]
