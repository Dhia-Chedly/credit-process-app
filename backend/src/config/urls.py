from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/health/", include("apps.core.urls")),
    path("api/import-batches/", include("apps.imports.urls")),
    path("api/credit-requests/", include("apps.applications.urls")),
    path("api/dashboard/", include("apps.analytics.urls")),
    path("api/reference-data/", include("apps.warehouse.urls")),
    path("api/delay-alerts/", include("apps.alerts.urls")),
    path("api/assistant/", include("apps.assistant.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
