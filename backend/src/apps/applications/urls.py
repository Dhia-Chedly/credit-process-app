from rest_framework.routers import DefaultRouter

from apps.applications.views import CreditRequestViewSet

app_name = "applications"

router = DefaultRouter()
router.register("", CreditRequestViewSet, basename="credit-request")

urlpatterns = router.urls
