from typing import Any
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(serializers.CharField())
class CSVUUIDListField(serializers.Field[tuple[UUID, ...], Any, list[str], Any]):
    """Accept a comma-separated UUID query parameter as a list."""

    def to_internal_value(self, data: Any) -> tuple[UUID, ...]:
        if not isinstance(data, str):
            self.fail("invalid")
        values = [value.strip() for value in data.split(",") if value.strip()]
        if not values:
            self.fail("invalid")
        uuid_field = serializers.UUIDField()
        return tuple(uuid_field.to_internal_value(value) for value in values)

    def to_representation(self, value: tuple[UUID, ...]) -> list[str]:
        return [str(item) for item in value]


class AnalyticsFilterSerializer(serializers.Serializer[dict[str, Any]]):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    agency = CSVUUIDListField(required=False)
    ca = serializers.UUIDField(required=False)
    gp = serializers.UUIDField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise serializers.ValidationError({"date_to": "date_to must be on or after date_from."})
        return attrs


class EmployeeFilterSerializer(AnalyticsFilterSerializer):
    role = serializers.ChoiceField(choices=("gp", "ca"), required=False)


class DelayFilterSerializer(AnalyticsFilterSerializer):
    interval = serializers.ChoiceField(
        choices=(
            "request_to_reception",
            "reception_to_assignment",
            "assignment_to_visit",
            "visit_to_outcome",
            "request_to_outcome",
            "request_to_disbursement",
            "request_to_rejection",
        ),
        required=False,
    )


class AnalyticsEnvelopeSerializer(serializers.Serializer[dict[str, Any]]):
    """OpenAPI boundary for aggregate-only analytics responses."""

    filters = serializers.JSONField()
    completeness = serializers.JSONField()
    results = serializers.JSONField(required=False)
    summary = serializers.JSONField(required=False)
    intervals = serializers.JSONField(required=False)
    aging = serializers.JSONField(required=False)


class AnalyticsMetadataSerializer(serializers.Serializer[dict[str, Any]]):
    date_range = serializers.JSONField()
    agencies = serializers.JSONField()
    statuses = serializers.JSONField()
    intervals = serializers.JSONField()
    employee_roles = serializers.JSONField()
    definitions = serializers.JSONField()
    completeness = serializers.JSONField()
