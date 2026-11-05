from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from apps.warehouse.crypto import normalize_match_value
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditTypeDimension,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    SelectableDimension,
)


class AgencyReferenceSerializer(serializers.ModelSerializer[AgencyDimension]):
    class Meta:
        model = AgencyDimension
        fields = ("id", "name", "code", "is_active")
        read_only_fields = fields


class EmployeeReferenceSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    agency_id = serializers.UUIDField(read_only=True)
    role = serializers.ChoiceField(choices=("ca", "gp"), read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class AgencyCreateSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    code = serializers.RegexField(r"^\d{4}$")

    def validate_name(self, value: str) -> str:
        name = value.strip()
        normalized = normalize_match_value(name)
        if not normalized:
            raise serializers.ValidationError("Enter an agency name.")
        if any(
            agency.is_active and normalize_match_value(agency.name) == normalized
            for agency in AgencyDimension.objects.all()
        ):
            raise serializers.ValidationError("An agency with this name already exists.")
        return name

    def validate_code(self, value: str) -> str:
        existing = AgencyDimension.objects.filter(code=value).first()
        submitted_name = self.initial_data.get("name", "")
        if existing is not None and normalize_match_value(existing.name) != normalize_match_value(
            str(submitted_name)
        ):
            raise serializers.ValidationError("An agency with this code already exists.")
        return value


class AgencyCodeUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    code = serializers.RegexField(r"^\d{4}$", required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide an agency code or active status.")
        return attrs

    def validate_code(self, value: str) -> str:
        instance = cast(AgencyDimension | None, self.instance)
        agencies = AgencyDimension.objects.filter(code=value)
        if isinstance(instance, AgencyDimension):
            agencies = agencies.exclude(pk=instance.pk)
        if agencies.exists():
            raise serializers.ValidationError("An agency with this code already exists.")
        return value


class EmployeeCreateSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    agency_id = serializers.PrimaryKeyRelatedField(
        queryset=AgencyDimension.objects.filter(is_active=True),
        source="agency",
    )
    role = serializers.ChoiceField(choices=("ca", "gp"))

    def validate_name(self, value: str) -> str:
        name = value.strip()
        normalized = normalize_match_value(name)
        if not normalized:
            raise serializers.ValidationError("Enter an employee name.")
        if normalized == normalize_match_value("Inconnu"):
            raise serializers.ValidationError(
                "The reserved Inconnu member cannot be created manually."
            )
        return name

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        agency = attrs["agency"]
        model = CADimension if attrs["role"] == "ca" else GPDimension
        normalized = normalize_match_value(attrs["name"])
        if any(
            employee.is_active and normalize_match_value(employee.name) == normalized
            for employee in model.objects.filter(agency=agency)
        ):
            raise serializers.ValidationError(
                {"name": "This employee already exists for the selected agency and role."}
            )
        return attrs


class EmployeeUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    agency_id = serializers.PrimaryKeyRelatedField(
        queryset=AgencyDimension.objects.filter(is_active=True),
        source="agency",
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide an agency, email, or active status.")
        return attrs


class SelectableReferenceSerializer(serializers.Serializer[SelectableDimension]):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class SelectableReferenceCreateSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=160, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not normalize_match_value(name):
            raise serializers.ValidationError("Enter a reference value.")
        return name


SELECTABLE_REFERENCE_MODELS: dict[
    str,
    type[CreditTypeDimension]
    | type[ActivityDimension]
    | type[RequestTypeDimension]
    | type[RejectionReasonDimension],
] = {
    "credit-types": CreditTypeDimension,
    "activities": ActivityDimension,
    "request-types": RequestTypeDimension,
    "rejection-reasons": RejectionReasonDimension,
}
