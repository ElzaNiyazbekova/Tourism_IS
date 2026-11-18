"""Health probe for NFR-02 (availability). Owner: Dastan (Testing & Integration)."""
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    """200 + db ok when the app and the database both answer; 503 otherwise."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception:  # noqa: BLE001 - any DB failure means "not healthy"
        db = "down"
    body = {"status": "ok" if db == "ok" else "degraded", "db": db, "time": timezone.now().isoformat()}
    return JsonResponse(body, status=200 if db == "ok" else 503)


def spa_index(request, *args, **kwargs):
    """Production only (FRONTEND_DIST set): any non-API page (/tours/3, /admin/tours ...) gets Angular's index.html,
    and the Angular router shows the right screen. Never cached, so a new deploy is picked up at once."""
    from pathlib import Path

    from django.conf import settings
    from django.http import FileResponse, Http404

    index = Path(settings.FRONTEND_DIST) / "index.html"
    if not index.is_file():
        raise Http404("Frontend build not found")
    resp = FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    return resp
