"""URL map. Everything lives under /api/ (plus /health for monitors). Owner: Amina A."""
from django.conf import settings
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from core.views import health, spa_index

urlpatterns = [
    path("health", health),                                   # NFR-02 availability probe
    path("api/health", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema")),
    path("api/", include("accounts.urls")),
    path("api/admin/", include("catalog.admin_urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("bookings.urls")),
    path("api/", include("flexbook.urls")),                   # FlexBook add-on
]

if settings.FRONTEND_DIST:      # production: everything that is not the API / docs / static is the Angular app
    urlpatterns.append(re_path(r"^(?!api/|health$|static/).*$", spa_index))
