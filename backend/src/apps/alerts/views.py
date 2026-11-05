from typing import Any, cast

from django.db.models import Count, QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.alerts.models import DelayAlert
from apps.alerts.serializers import DelayAlertSerializer
from apps.applications.permissions import ApplicationReadPermission
from apps.core.permissions import ImportBatchPermission


class DelayAlertViewSet(viewsets.ReadOnlyModelViewSet[DelayAlert]):
    permission_classes = [ApplicationReadPermission]
    serializer_class = DelayAlertSerializer
    queryset = DelayAlert.objects.select_related("agency", "credit_request")

    def get_permissions(self) -> list[BasePermission]:
        if self.action == "resolve":
            return [ImportBatchPermission()]
        return cast(list[BasePermission], list(super().get_permissions()))

    def _filter_queryset(
        self, queryset: QuerySet[DelayAlert], *, include_state: bool
    ) -> QuerySet[DelayAlert]:
        for key in ("agency", "state", "rule"):
            if key == "state" and not include_state:
                continue
            if value := self.request.query_params.get(key):
                queryset = queryset.filter(**{f"{key}_id" if key == "agency" else key: value})
        if responsible := self.request.query_params.get("responsible"):
            queryset = queryset.filter(responsible_name=responsible)
        if responsible_role := self.request.query_params.get("responsible_role"):
            queryset = queryset.filter(responsible_role=responsible_role)
        return queryset

    def get_queryset(self) -> QuerySet[DelayAlert]:
        return self._filter_queryset(super().get_queryset(), include_state=True).order_by(
            "started_on", "id"
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        all_alerts = super().get_queryset()
        scoped_alerts = self._filter_queryset(all_alerts, include_state=False)
        response = super().list(request, *args, **kwargs)
        if not isinstance(response.data, dict):
            return response
        state_counts = {
            row["state"]: row["count"]
            for row in scoped_alerts.values("state").annotate(count=Count("id"))
        }
        response.data["summary"] = {
            "new": state_counts.get(DelayAlert.State.NEW, 0),
            "escalated": state_counts.get(DelayAlert.State.ESCALATED, 0),
        }
        response.data["filter_options"] = {
            "agencies": list(
                all_alerts.order_by("agency__name").values("agency_id", "agency__name").distinct()
            ),
            "responsibles": list(
                all_alerts.order_by("agency__name", "responsible_name", "responsible_role")
                .values("agency_id", "agency__name", "responsible_name", "responsible_role")
                .distinct()
            ),
        }
        return response

    @action(detail=True, methods=["delete"])
    def resolve(self, _request: Request, pk: str | None = None) -> Response:
        """Remove an alert once an operator has resolved the operational follow-up."""
        del pk
        alert = self.get_object()
        alert.delete()
        return Response(status=204)
