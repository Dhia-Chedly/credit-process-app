from typing import Any

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, serializers, viewsets
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.applications.filters import CreditRequestFilter
from apps.applications.permissions import ApplicationReadPermission
from apps.applications.serializers import (
    CreditRequestDashboardSerializer,
    MaskedCreditRequestDetailSerializer,
)
from apps.warehouse.models import FactCreditRequest


class CreditRequestSearchFilter(filters.SearchFilter):
    """Search operational agency and canonical dossier-reference values."""

    def filter_queryset(
        self,
        request: Request,
        queryset: QuerySet[Any],
        _view: APIView,
    ) -> QuerySet[Any]:
        term = request.query_params.get(self.search_param, "").strip()
        if not term:
            return queryset
        return queryset.filter(agency__name__icontains=term) | queryset.filter(
            reference__icontains=term
        )


@extend_schema_view(
    retrieve=extend_schema(
        responses=MaskedCreditRequestDetailSerializer,
    )
)
class CreditRequestViewSet(viewsets.ReadOnlyModelViewSet[FactCreditRequest]):
    """Serve one current lifecycle fact per credit request within the caller's IAM scope."""

    permission_classes = [ApplicationReadPermission]
    serializer_class = CreditRequestDashboardSerializer
    filter_backends = (
        DjangoFilterBackend,
        CreditRequestSearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = CreditRequestFilter
    ordering_fields = (
        "request_date",
        "amount",
        "updated_at",
        "agency__name",
        "reference",
    )
    ordering = ("-request_date", "agency__name")
    lookup_field = "id"
    lookup_url_kwarg = "pk"
    queryset = FactCreditRequest.objects.filter(
        current_tb1_row__isnull=False,
        current_tb2_row__isnull=False,
    )

    def get_serializer_class(self) -> type[serializers.BaseSerializer[FactCreditRequest]]:
        if self.action != "retrieve":
            return CreditRequestDashboardSerializer
        return MaskedCreditRequestDetailSerializer

    def get_queryset(self) -> QuerySet[FactCreditRequest]:
        queryset = super().get_queryset()
        if self.action != "retrieve":
            return queryset.select_related("credit_type", "request_date", "status")
        return queryset.select_related(
            "agency",
            "gp",
            "ca_caa",
            "credit_type",
            "activity",
            "request_type",
            "status",
            "rejection_reason",
            "request_date",
            "reception_date",
            "gp_assignment_date",
            "visit_date",
            "disbursement_date",
            "rejection_date",
            "current_tb1_row",
            "current_tb1_row__batch",
            "current_tb2_row",
            "current_tb2_row__batch",
        ).prefetch_related("status_history__status", "status_history__effective_date")
