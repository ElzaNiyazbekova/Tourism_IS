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
