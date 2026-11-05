from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.imports.models import TB1RequestStagingRow, TB2SnapshotStagingRow
from apps.warehouse.models import (
    AgencyDimension,
    CreditRequestStatusHistory,
    FactCreditRequest,
    RejectionReasonDimension,
    StatusDimension,
)


class AgencySummarySerializer(serializers.ModelSerializer[AgencyDimension]):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = AgencyDimension
        fields = ("id", "name")
        read_only_fields = fields


class CreditRequestStatusSummarySerializer(serializers.ModelSerializer[StatusDimension]):
    label = serializers.CharField(source="name", read_only=True)  # type: ignore[assignment]
    is_financed = serializers.BooleanField(source="is_funded", read_only=True)

    class Meta:
        model = StatusDimension
        fields = (
            "id",
            "code",
            "label",
            "pipeline_stage",
            "is_terminal",
            "is_financed",
            "is_rejected",
        )
        read_only_fields = fields


class RejectionReasonSummarySerializer(serializers.ModelSerializer[RejectionReasonDimension]):
    class Meta:
        model = RejectionReasonDimension
        fields = ("id", "name")
        read_only_fields = fields


class SourceCompletenessSerializer(serializers.Serializer[Any]):
    matched = serializers.BooleanField(default=True, read_only=True)


class CurrentProvenanceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    batch_id = serializers.UUIDField(read_only=True)
    original_filename = serializers.CharField(allow_null=True, read_only=True)
    source_kind = serializers.ChoiceField(choices=("tb1", "tb2"), read_only=True)
    reporting_period = serializers.DateField(allow_null=True, read_only=True)
    sheet_name = serializers.CharField(allow_null=True, read_only=True)
    source_row = serializers.IntegerField(read_only=True)
    row_status = serializers.CharField(read_only=True)
    source_class_authoritative = serializers.BooleanField(read_only=True)
    controls_current_state = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class CreditRequestStatusHistorySerializer(serializers.ModelSerializer[CreditRequestStatusHistory]):
    status_code = serializers.CharField(source="status.code", read_only=True)
    status_label = serializers.CharField(source="status.name", read_only=True)
    effective_date = serializers.DateField(source="effective_date.calendar_date", read_only=True)
    source_tb1_row_id = serializers.UUIDField(read_only=True)
    source_tb2_row_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CreditRequestStatusHistory
        fields = (
            "id",
            "status_code",
            "status_label",
            "effective_date",
            "source_tb1_row_id",
            "source_tb2_row_id",
            "created_at",
        )
        read_only_fields = fields


def _governed_label(value: object) -> str:
    return str(getattr(value, "name", "") or "")


def _employee_label(fact: FactCreditRequest, attribute: str, _context: dict[str, Any]) -> str:
    employee = getattr(fact, attribute, None)
    if employee is None:
        return ""
    # Staff assignment is operational reference data, not client-identifying data.
    return str(employee.name)


def _provenance_entry(
    *,
    _fact: FactCreditRequest,
    row: TB1RequestStagingRow | TB2SnapshotStagingRow,
    source_kind: str,
) -> dict[str, object]:
    return {
        "id": row.pk,
        "batch_id": row.batch_id,
        # Workbook names and sheet labels are deliberately withheld from this dashboard API.
        "original_filename": None,
        "source_kind": source_kind,
        "reporting_period": row.reporting_period,
        "sheet_name": None,
        "source_row": row.source_row,
        "row_status": row.status,
        "source_class_authoritative": source_kind == "tb2",
        "controls_current_state": True,
        "created_at": row.batch.created_at,
    }


class CreditRequestListSerializer(serializers.ModelSerializer[FactCreditRequest]):
    public_id = serializers.UUIDField(source="id", read_only=True)
    agency = AgencySummarySerializer(read_only=True)
    reference = serializers.CharField(read_only=True)
    display_reference = serializers.CharField(source="reference", read_only=True)
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
        allow_null=True,
        read_only=True,
    )
    credit_type = serializers.SerializerMethodField()
    request_type = serializers.SerializerMethodField()
    activity_category = serializers.SerializerMethodField()
    request_date = serializers.DateField(
        source="request_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    gp_name = serializers.SerializerMethodField()
    counsellor_name = serializers.SerializerMethodField()
    disbursement_date = serializers.DateField(
        source="disbursement_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    rejection_date = serializers.DateField(
        source="rejection_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    missing_from_latest_tb2_period = serializers.DateField(allow_null=True, read_only=True)
    status = CreditRequestStatusSummarySerializer(read_only=True)
    source_completeness = serializers.SerializerMethodField()

    class Meta:
        model = FactCreditRequest
        fields: tuple[str, ...] = (
            "id",
            "public_id",
            "agency",
            "reference",
            "display_reference",
            "amount",
            "credit_type",
            "request_type",
            "activity_category",
            "request_date",
            "gp_name",
            "counsellor_name",
            "disbursement_date",
            "rejection_date",
            "missing_from_latest_tb2_period",
            "status",
            "source_completeness",
            "updated_at",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(serializers.CharField())
    def get_credit_type(self, obj: FactCreditRequest) -> str:
        return _governed_label(obj.credit_type)

    @extend_schema_field(serializers.CharField())
    def get_request_type(self, obj: FactCreditRequest) -> str:
        return _governed_label(obj.request_type)

    @extend_schema_field(serializers.CharField())
    def get_activity_category(self, obj: FactCreditRequest) -> str:
        return _governed_label(obj.activity)

    @extend_schema_field(serializers.CharField())
    def get_gp_name(self, obj: FactCreditRequest) -> str:
        return _employee_label(obj, "gp", self.context)

    @extend_schema_field(serializers.CharField())
    def get_counsellor_name(self, obj: FactCreditRequest) -> str:
        return _employee_label(obj, "ca_caa", self.context)

    @extend_schema_field(SourceCompletenessSerializer)
    def get_source_completeness(self, obj: FactCreditRequest) -> dict[str, object]:
        return dict(SourceCompletenessSerializer(obj).data)


class CreditRequestDashboardSerializer(serializers.ModelSerializer[FactCreditRequest]):
    """Minimal representation used by the operational dossier list."""

    public_id = serializers.UUIDField(source="id", read_only=True)
    display_reference = serializers.CharField(source="reference", read_only=True)
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
        allow_null=True,
        read_only=True,
    )
    credit_type = serializers.CharField(source="credit_type.name", allow_null=True, read_only=True)
    request_date = serializers.DateField(
        source="request_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    status = CreditRequestStatusSummarySerializer(read_only=True)

    class Meta:
        model = FactCreditRequest
        fields = (
            "id",
            "public_id",
            "reference",
            "display_reference",
            "amount",
            "credit_type",
            "request_date",
            "status",
        )
        read_only_fields = fields


class _CreditRequestDetailBase(CreditRequestListSerializer):
    received_at_agency_date = serializers.DateField(
        source="reception_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    assigned_to_gp_date = serializers.DateField(
        source="gp_assignment_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    visit_date = serializers.DateField(
        source="visit_date.calendar_date",
        allow_null=True,
        read_only=True,
    )
    history_scope = serializers.CharField(default="current_provenance", read_only=True)
    source_history = serializers.SerializerMethodField()
    status_history = CreditRequestStatusHistorySerializer(many=True)

    class Meta(CreditRequestListSerializer.Meta):
        fields: tuple[str, ...] = (
            *CreditRequestListSerializer.Meta.fields,
            "received_at_agency_date",
            "assigned_to_gp_date",
            "visit_date",
            "history_scope",
            "source_history",
            "status_history",
            "created_at",
        )
        read_only_fields: tuple[str, ...] = fields

    @extend_schema_field(CurrentProvenanceSerializer(many=True))
    def get_source_history(self, obj: FactCreditRequest) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        if obj.current_tb1_row is not None:
            entries.append(_provenance_entry(_fact=obj, row=obj.current_tb1_row, source_kind="tb1"))
        if obj.current_tb2_row is not None:
            entries.append(_provenance_entry(_fact=obj, row=obj.current_tb2_row, source_kind="tb2"))
        return [dict(item) for item in CurrentProvenanceSerializer(entries, many=True).data]


class MaskedCreditRequestDetailSerializer(_CreditRequestDetailBase):
    """Operational current state without client-identifying information."""
