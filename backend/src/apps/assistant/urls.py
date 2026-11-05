from django.urls import path

from apps.assistant.views import AssistantView

app_name = "assistant"

urlpatterns = [path("messages/", AssistantView.as_view(), name="messages")]
