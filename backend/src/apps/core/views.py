from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView

from apps.core.serializers import LiveHealthSerializer, ReadyHealthSerializer


class LiveHealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(responses={HTTP_200_OK: LiveHealthSerializer})
    def get(self, _request: Request) -> Response:
        return Response({"service": "microcrd-api", "status": "ok"}, status=HTTP_200_OK)


class ReadyHealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            HTTP_200_OK: ReadyHealthSerializer,
            HTTP_503_SERVICE_UNAVAILABLE: ReadyHealthSerializer,
        }
    )
    def get(self, _request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response(
                {"database": "unavailable", "service": "microcrd-api", "status": "error"},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {"database": "ok", "service": "microcrd-api", "status": "ok"},
            status=HTTP_200_OK,
        )
