from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

from django.db import transaction

from apps.imports.models import (
    StagingRowStatus,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
)
from apps.imports.parser import WorkbookKind
from apps.warehouse.crypto import normalize_match_value
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditRequestStatusHistory,
    CreditTypeDimension,
    DateDimension,
    FactCreditRequest,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    StatusDimension,
)

StageRow = TB1RequestStagingRow | TB2SnapshotStagingRow


@dataclass(frozen=True, slots=True)
class WarehouseLoadIssue:
    code: str
    message: str
    field: str = ""


@dataclass(frozen=True, slots=True)
class WarehouseLoadResult:
    fact: FactCreditRequest
    stale: bool
    issues: tuple[WarehouseLoadIssue, ...]


class WarehouseLoadError(ValueError):
    def __init__(self, code: str, message: str, field: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.field = field


STATUS_DEFINITIONS: dict[str, dict[str, object]] = {
    "registered": {
        "name": "Demande enregistrée",
        "pipeline_stage": StatusDimension.PipelineStage.INTAKE,
    },
    "received": {
        "name": "Demande reçue",
        "pipeline_stage": StatusDimension.PipelineStage.INTAKE,
    },
    "awaiting_gp_assignment": {
        "name": "En attente d\u2019affectation à un GP",
        "pipeline_stage": StatusDimension.PipelineStage.INTAKE,
    },
    "awaiting_visit": {
        "name": "En attente de visite",
        "pipeline_stage": StatusDimension.PipelineStage.WAITING_VISIT,
    },
    "awaiting_decision": {
        "name": "En attente de décision",
        "pipeline_stage": StatusDimension.PipelineStage.WAITING_DECISION,
    },
    "funded": {
        "name": "Décaissé",
        "pipeline_stage": StatusDimension.PipelineStage.COMPLETED,
        "is_terminal": True,
        "is_funded": True,
    },
    "rejected": {
        "name": "Rejeté",
        "pipeline_stage": StatusDimension.PipelineStage.COMPLETED,
        "is_terminal": True,
        "is_rejected": True,
    },
}


@transaction.atomic
def load_credit_request(
    *,
    stage: StageRow,
    data: Mapping[str, object],
    source_kind: WorkbookKind,
    created_fact_id: UUID | None = None,
) -> WarehouseLoadResult:
    """Publish one committed typed source row into the lifecycle fact."""

    if stage.status != StagingRowStatus.COMMITTED:
        raise WarehouseLoadError(
            "uncommitted_staging_row",
            "Only an accepted staging row may update the reporting warehouse.",
        )
    agency = stage.detected_agency
    if agency is None:
        raise WarehouseLoadError("missing_agency", "A governed agency is required.", "agency")
    reference = _required_text(data, "reference")
    exact_tb1_fact = (
        FactCreditRequest.objects.filter(
            agency=agency,
            reference=reference,
            current_tb1_row__isnull=False,
        )
        .select_related("agency", "request_date")
        .first()
        if source_kind is WorkbookKind.TB2
        else None
    )
    fact: FactCreditRequest | None
    if exact_tb1_fact is not None:
        # The natural TB2 form deliberately does not repeat TB1 request facts.
        # Its official agency code and request reference are sufficient for an
        # exact join; the original request date and amount remain owned by TB1.
        request_date_dimension = exact_tb1_fact.request_date
        if request_date_dimension is None:
            raise WarehouseLoadError(
                "tb1_missing_request_date",
                "The linked TB1 request has no usable request date.",
                "request_date",
            )
        fact = exact_tb1_fact
        amount = fact.amount
        request_date = request_date_dimension.calendar_date
        agency_dimension = fact.agency
        fact = exact_tb1_fact
    else:
        amount = _required_decimal(data, "amount")
        request_date = _required_date(data, "request_date")
        agency_dimension = agency
        fact = FactCreditRequest.objects.filter(agency=agency, reference=reference).first()
    created = fact is None
    issues: list[WarehouseLoadIssue] = []

    if created:
        if source_kind is WorkbookKind.TB2:
            raise WarehouseLoadError(
                "tb2_without_tb1_match",
                "Only exact TB1/TB2 pairs may be published.",
                "reference",
            )
        fact = FactCreditRequest(
            agency=agency_dimension,
            reference=reference,
            amount=amount,
            request_date=_date_dimension(request_date),
        )
        if created_fact_id is not None:
            fact.pk = created_fact_id
    else:
        assert fact is not None
        fact = FactCreditRequest.objects.select_for_update().get(pk=fact.pk)

    assert fact is not None
    if source_kind is WorkbookKind.TB1:
        if not isinstance(stage, TB1RequestStagingRow):
            raise WarehouseLoadError(
                "source_staging_mismatch",
                "A TB1 load requires a TB1 staging row.",
            )
        fact.agency = agency_dimension
        _apply_request_facts(fact=fact, data=data, issues=issues)
        fact.current_tb1_row = stage
    else:
        if not isinstance(stage, TB2SnapshotStagingRow):
            raise WarehouseLoadError(
                "source_staging_mismatch",
                "A TB2 load requires a TB2 staging row.",
            )
        if fact.current_tb1_row_id is None:
            fact.agency = agency_dimension
            _apply_request_facts(fact=fact, data=data, issues=issues)
        _apply_outcome_facts(fact=fact, data=data, issues=issues)
        fact.current_tb2_row = stage
    _derive_status_from_dates(fact=fact, source_kind=source_kind)
    fact.full_clean()
    fact.save()
    _record_status_history(fact=fact, stage=stage)
    return WarehouseLoadResult(
        fact=fact,
        stale=False,
        issues=tuple(issues),
    )


def _apply_request_facts(
    *,
    fact: FactCreditRequest,
    data: Mapping[str, object],
    issues: list[WarehouseLoadIssue],
) -> None:
    fact.reference = _required_text(data, "reference")
    fact.amount = _required_decimal(data, "amount")
    fact.request_date = _date_dimension(_required_date(data, "request_date"))
    fact.credit_type = cast(
        CreditTypeDimension | None,
        _governed_dimension(
            raw_value=data.get("credit_type"),
            target_model=CreditTypeDimension,
            field="credit_type",
            issues=issues,
        ),
    )
    fact.activity = cast(
        ActivityDimension | None,
        _governed_dimension(
            raw_value=data.get("activity_category"),
            target_model=ActivityDimension,
            field="activity_category",
            issues=issues,
        ),
    )
    fact.request_type = cast(
        RequestTypeDimension | None,
        _governed_dimension(
            raw_value=data.get("request_type"),
            target_model=RequestTypeDimension,
            field="request_type",
            issues=issues,
        ),
    )


def _apply_outcome_facts(
    *,
    fact: FactCreditRequest,
    data: Mapping[str, object],
    issues: list[WarehouseLoadIssue],
) -> None:
    fact.reception_date = _date_dimension(_optional_date(data.get("received_at_agency_date")))
    fact.gp_assignment_date = _date_dimension(_optional_date(data.get("assigned_to_gp_date")))
    fact.visit_date = _date_dimension(_optional_date(data.get("visit_date")))
    fact.disbursement_date = _date_dimension(_optional_date(data.get("disbursement_date")))
    fact.rejection_date = _date_dimension(_optional_date(data.get("rejection_date")))
    fact.rejection_reason = (
        cast(
            RejectionReasonDimension | None,
            _governed_dimension(
                raw_value=data.get("rejection_reason"),
                target_model=RejectionReasonDimension,
                field="rejection_reason",
                issues=issues,
            ),
        )
        if fact.rejection_date is not None
        else None
    )
    fact.gp = (
        cast(
            GPDimension,
            _staff_dimension(
                agency=fact.agency,
                raw_value=data.get("gp_name"),
                dimension_model=GPDimension,
                field="gp_name",
            ),
        )
        if fact.gp_assignment_date is not None
        else None
    )
    fact.ca_caa = (
        cast(
            CADimension,
            _staff_dimension(
                agency=fact.agency,
                raw_value=data.get("counsellor_name"),
                dimension_model=CADimension,
                field="counsellor_name",
            ),
        )
        if fact.reception_date is not None
        else None
    )


def _staff_dimension(
    *,
    agency: AgencyDimension,
    raw_value: object,
    dimension_model: type[CADimension] | type[GPDimension],
    field: str,
) -> CADimension | GPDimension:
    value = _optional_text(raw_value)
    role = "CA/CAA" if dimension_model is CADimension else "GP"
    if not value:
        raise WarehouseLoadError(
            "missing_employee_identity",
            f"A {role} name is required and must match an active {role} employee in the agency.",
            field,
        )
    if normalize_match_value(value) == normalize_match_value("Inconnu"):
        raise WarehouseLoadError(
            "unresolved_employee_identity",
            f"The {role} name must match exactly one active {role} employee in the agency.",
            field,
        )
    matches = _matching_staff_dimensions(
        agency=agency,
        value=value,
        dimension_model=dimension_model,
    )
    if len(matches) == 1:
        return matches[0]
    raise WarehouseLoadError(
        "unresolved_employee_identity",
        f"The {role} name must match exactly one active {role} employee in the agency.",
        field,
    )


def _matching_staff_dimensions(
    *,
    agency: AgencyDimension,
    value: str,
    dimension_model: type[CADimension] | type[GPDimension],
) -> list[CADimension | GPDimension]:
    if not value:
        return []
    normalized = normalize_match_value(value)
    return [
        staff
        for staff in dimension_model.objects.filter(
            agency=agency,
            is_active=True,
        ).select_related("agency")
        if normalize_match_value(staff.name) == normalized
    ]


def _derive_status_from_dates(*, fact: FactCreditRequest, source_kind: WorkbookKind) -> None:
    if fact.disbursement_date is not None and fact.rejection_date is not None:
        raise WarehouseLoadError(
            "conflicting_terminal_outcomes",
            "A request cannot have both a disbursement date and a rejection date.",
            "disbursement_date",
        )

    status_code: str
    effective_date: DateDimension | None
    if fact.disbursement_date is not None:
        status_code, effective_date = "funded", fact.disbursement_date
    elif fact.rejection_date is not None:
        status_code, effective_date = "rejected", fact.rejection_date
    elif fact.visit_date is not None:
        status_code, effective_date = "awaiting_decision", fact.visit_date
    elif fact.gp_assignment_date is not None:
        status_code, effective_date = "awaiting_visit", fact.gp_assignment_date
    elif fact.reception_date is not None:
        status_code, effective_date = "awaiting_gp_assignment", fact.reception_date
    elif source_kind is WorkbookKind.TB2:
        status_code, effective_date = "received", fact.request_date
    else:
        status_code, effective_date = "registered", fact.request_date

    if effective_date is None:
        raise WarehouseLoadError(
            "missing_status_effective_date",
            "A request date is required to derive lifecycle status.",
            "request_date",
        )

    fact.status = _status_dimension(status_code)
    if status_code != "rejected":
        fact.rejection_reason = None


def _record_status_history(*, fact: FactCreditRequest, stage: StageRow) -> None:
    effective_date = (
        fact.rejection_date
        or fact.disbursement_date
        or fact.visit_date
        or fact.gp_assignment_date
        or fact.reception_date
        or fact.request_date
    )
    if fact.status is None or effective_date is None:
        return
    last_entry = fact.status_history.order_by("-effective_date_id", "-created_at", "-id").first()
    if last_entry is not None and last_entry.status_id == fact.status_id:
        return
    CreditRequestStatusHistory.objects.create(
        credit_request=fact,
        status=fact.status,
        effective_date=effective_date,
        source_tb1_row=stage if isinstance(stage, TB1RequestStagingRow) else None,
        source_tb2_row=stage if isinstance(stage, TB2SnapshotStagingRow) else None,
    )


def _governed_dimension(
    *,
    raw_value: object,
    target_model: type[CreditTypeDimension]
    | type[ActivityDimension]
    | type[RequestTypeDimension]
    | type[RejectionReasonDimension],
    field: str,
    issues: list[WarehouseLoadIssue],
) -> (
    CreditTypeDimension | ActivityDimension | RequestTypeDimension | RejectionReasonDimension | None
):
    value = _optional_text(raw_value)
    target = _direct_dimension_match(value=value, target_model=target_model) if value else None
    if target is not None:
        return cast(
            CreditTypeDimension
            | ActivityDimension
            | RequestTypeDimension
            | RejectionReasonDimension,
            target,
        )
    _ = issues
    raise WarehouseLoadError(
        "unresolved_dimension_value",
        "The value must match exactly one active reference-data entry.",
        field,
    )


def _direct_dimension_match(
    *,
    value: str,
    target_model: type[CreditTypeDimension]
    | type[ActivityDimension]
    | type[RequestTypeDimension]
    | type[StatusDimension]
    | type[RejectionReasonDimension],
) -> (
    CreditTypeDimension
    | ActivityDimension
    | RequestTypeDimension
    | StatusDimension
    | RejectionReasonDimension
    | None
):
    normalized = normalize_match_value(value)
    matches = [
        dimension
        for dimension in target_model.objects.filter(is_active=True)
        if normalize_match_value(dimension.name) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _status_dimension(code: str) -> StatusDimension:
    defaults = STATUS_DEFINITIONS[code]
    status, _created = StatusDimension.objects.update_or_create(code=code, defaults=defaults)
    return status


def ensure_status_dimensions() -> dict[str, StatusDimension]:
    """Seed the governed lifecycle states used by deterministic source classification."""

    return {code: _status_dimension(code) for code in STATUS_DEFINITIONS}


def _date_dimension(value: date | None) -> DateDimension | None:
    if value is None:
        return None
    dimension, _created = DateDimension.objects.get_or_create(calendar_date=value)
    return dimension


def _required_text(data: Mapping[str, object], field: str) -> str:
    value = _optional_text(data.get(field))
    if not value:
        raise WarehouseLoadError(
            "invalid_required_text",
            f"The normalized {field} value is missing.",
            field,
        )
    return value


def _required_decimal(data: Mapping[str, object], field: str) -> Decimal:
    value = _optional_decimal(data.get(field))
    if value is None:
        raise WarehouseLoadError(
            "invalid_required_decimal",
            f"The normalized {field} value is missing.",
            field,
        )
    return value


def _required_date(data: Mapping[str, object], field: str) -> date:
    value = _optional_date(data.get(field))
    if value is None:
        raise WarehouseLoadError(
            "invalid_required_date",
            f"The normalized {field} value is missing.",
            field,
        )
    return value


def _optional_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float | str) and str(value).strip():
        try:
            return Decimal(str(value))
        except ArithmeticError:
            return None
    return None


def _optional_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
