"""URL map. Everything lives under /api/ (plus /health for monitors). Owner: Amina A."""
from django.urls import include, path
from django.contrib import admin
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from core.views import health

urlpatterns = [
    path("health", health),                                   # NFR-02 availability probe
    path("api/health", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema")),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("bookings.urls")),
]
