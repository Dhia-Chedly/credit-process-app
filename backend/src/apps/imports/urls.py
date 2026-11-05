from rest_framework.routers import DefaultRouter

from apps.imports.views import ImportBatchViewSet

app_name = "imports"

router = DefaultRouter()
router.register("", ImportBatchViewSet, basename="import-batch")

urlpatterns = router.urls
