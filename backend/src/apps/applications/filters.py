from datetime import date

import django_filters
from django.db.models import QuerySet

from apps.warehouse.models import FactCreditRequest


class UUIDInFilter(django_filters.BaseInFilter, django_filters.UUIDFilter):  # type: ignore[misc]
    pass


class CreditRequestFilter(django_filters.FilterSet):  # type: ignore[misc]
    """Public dashboard filters mapped only to governed warehouse attributes."""

    agency = UUIDInFilter(field_name="agency_id", lookup_expr="in")
    ca = UUIDInFilter(field_name="ca_caa_id", lookup_expr="in")
    gp = UUIDInFilter(field_name="gp_id", lookup_expr="in")
    status = django_filters.UUIDFilter(field_name="status_id")
    credit_type = django_filters.CharFilter(field_name="credit_type__code")
    request_type = django_filters.CharFilter(field_name="request_type__code")
    activity_category = django_filters.CharFilter(field_name="activity__name")
    request_date_from = django_filters.DateFilter(
        field_name="request_date__calendar_date",
        lookup_expr="gte",
    )
    request_date_to = django_filters.DateFilter(method="filter_request_date_to")

    def filter_request_date_to(
        self,
        queryset: QuerySet[FactCreditRequest],
        _name: str,
        value: date,
    ) -> QuerySet[FactCreditRequest]:
        year = value.year
        month = value.month
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        return queryset.filter(request_date__calendar_date__lt=date(next_year, next_month, 1))

    class Meta:
        model = FactCreditRequest
        fields = (
            "agency",
            "ca",
            "gp",
            "status",
            "credit_type",
            "request_type",
            "activity_category",
            "request_date_from",
            "request_date_to",
        )
