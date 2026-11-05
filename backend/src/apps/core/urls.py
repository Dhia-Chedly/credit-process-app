from django.urls import path

from apps.core.views import LiveHealthView, ReadyHealthView

app_name = "health"

urlpatterns = [
    path("live/", LiveHealthView.as_view(), name="live"),
    path("ready/", ReadyHealthView.as_view(), name="ready"),
]
