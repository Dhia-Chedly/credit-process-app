from collections.abc import Mapping
from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from apps.analytics import services
from apps.analytics.serializers import (
    AnalyticsEnvelopeSerializer,
    AnalyticsFilterSerializer,
    AnalyticsMetadataSerializer,
    DelayFilterSerializer,
    EmployeeFilterSerializer,
)
from apps.core.permissions import AnalyticsPermission


def _filters(
    request: Request,
    serializer_class: type[Serializer[Any]] = AnalyticsFilterSerializer,
) -> tuple[services.AnalyticsFilters, Mapping[str, object]]:
    serializer = serializer_class(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    values = cast(Mapping[str, object], serializer.validated_data)
    return services.AnalyticsFilters.from_validated(values, user=request.user), values


class AnalyticsView(APIView):
    permission_classes = [AnalyticsPermission]


class MetadataView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsMetadataSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(services.metadata(filters))


class OverviewView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(services.response_payload(filters, summary=services.overview(filters)))


class PipelineView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(services.response_payload(filters, results=services.pipeline(filters)))


class AgencyComparisonView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(
            services.response_payload(filters, results=services.agency_comparison(filters))
        )


class EmployeeComparisonView(AnalyticsView):
    @extend_schema(
        parameters=[EmployeeFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, values = _filters(request, EmployeeFilterSerializer)
        role_value = values.get("role")
        role = role_value if isinstance(role_value, str) else None
        results, suppressed_groups = services.employee_comparison(filters, role=role)
        limitations: list[dict[str, str]] = []
        if suppressed_groups:
            limitations.append(
                {
                    "code": "employee_groups_suppressed",
                    "message": (
                        "Low-frequency employee source labels are combined into an "
                        "insufficient-sample bucket."
                    ),
                }
            )
        return Response(
            services.response_payload(
                filters,
                results=results,
                extra_limitations=limitations,
            )
        )


class DelayAndAgingView(AnalyticsView):
    @extend_schema(
        parameters=[DelayFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, values = _filters(request, DelayFilterSerializer)
        interval_value = values.get("interval")
        interval = interval_value if isinstance(interval_value, str) else None
        interval_rows, aging_rows = services.delays(filters, interval=interval)
        payload = services.response_payload(filters)
        payload["intervals"] = interval_rows
        payload["aging"] = aging_rows
        return Response(payload)


class RejectionView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        results, suppressed_groups = services.rejections(filters)
        limitations: list[dict[str, str]] = []
        if suppressed_groups:
            limitations.append(
                {
                    "code": "rejection_groups_suppressed",
                    "message": (
                        "Low-frequency rejection groups are combined to protect source text."
                    ),
                }
            )
        return Response(
            services.response_payload(
                filters,
                results=results,
                extra_limitations=limitations,
            )
        )


class ActivityView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(services.response_payload(filters, results=services.activities(filters)))


class ProductsAndRequestsView(AnalyticsView):
    @extend_schema(
        parameters=[AnalyticsFilterSerializer],
        responses={200: AnalyticsEnvelopeSerializer},
    )
    def get(self, request: Request) -> Response:
        filters, _values = _filters(request)
        return Response(
            services.response_payload(filters, results=services.products_and_requests(filters))
        )
