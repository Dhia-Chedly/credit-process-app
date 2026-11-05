from rest_framework.routers import DefaultRouter

from apps.alerts.views import DelayAlertViewSet

router = DefaultRouter()
router.register("", DelayAlertViewSet, basename="delay-alert")
urlpatterns = router.urls
