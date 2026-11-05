from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.assistant.serializers import AssistantRequestSerializer, AssistantResponseSerializer
from apps.assistant.services import AssistantUnavailableError, answer_question
from apps.core.permissions import has_active_user


class AssistantPermission(BasePermission):
    def has_permission(self, request: Request, _view: APIView) -> bool:
        return request.method == "POST" and has_active_user(request.user)


class AssistantView(APIView):
    permission_classes = [AssistantPermission]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant"

    @extend_schema(request=AssistantRequestSerializer, responses={200: AssistantResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = AssistantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            answer = answer_question(
                message=values["message"],
                history=list(values.get("history", [])),
                user=request.user,
            )
        except AssistantUnavailableError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(AssistantResponseSerializer(answer).data)
