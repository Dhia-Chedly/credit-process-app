import pytest
from django.db import IntegrityError, transaction

from apps.applications.serializers import CreditRequestStatusSummarySerializer
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import (
    ImportBatch,
    MatchStatus,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
)
from apps.imports.services import _block_pair
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditTypeDimension,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    StatusDimension,
)
from apps.warehouse.services import (
    STATUS_DEFINITIONS,
    WarehouseLoadError,
    _governed_dimension,
    _staff_dimension,
    ensure_status_dimensions,
)


@pytest.mark.django_db
def test_staging_coordinates_are_unique_per_sheet() -> None:
    batch = ImportBatch.objects.create(
        original_filename="multi-sheet.xlsx",
        source_file="imports/multi-sheet.xlsx",
        checksum_sha256="a" * 64,
        file_size=1,
    )
    january = TB1RequestStagingRow.objects.create(
        batch=batch,
        sheet_name="JANVIER 2026",
        source_row=2,
        row_hash="b" * 64,
    )
    february = TB1RequestStagingRow.objects.create(
        batch=batch,
        sheet_name="FEVRIER 2026",
        source_row=2,
        row_hash="c" * 64,
    )

    assert january.pk != february.pk
    with pytest.raises(IntegrityError), transaction.atomic():
        TB1RequestStagingRow.objects.create(
            batch=batch,
            sheet_name="JANVIER 2026",
            source_row=2,
            row_hash="d" * 64,
        )


@pytest.mark.django_db
def test_staging_row_agency_overrides_the_batch_agency_for_multi_agency_workbooks() -> None:
    batch_agency = AgencyDimension.objects.create(name="Batch agency")
    sheet_agency = AgencyDimension.objects.create(name="Sheet agency")
    batch = ImportBatch.objects.create(
        original_filename="all-agencies.xlsx",
        source_file="imports/all-agencies.xlsx",
        checksum_sha256="e" * 64,
        file_size=1,
        detected_agency=batch_agency,
    )
    row = TB1RequestStagingRow.objects.create(
        batch=batch,
        agency=sheet_agency,
        sheet_name="Sheet agency",
        source_row=2,
        row_hash="f" * 64,
    )

    assert row.detected_agency == sheet_agency


@pytest.mark.django_db
def test_ambiguous_pair_quarantines_each_row_without_duplicate_quality_issues() -> None:
    agency = AgencyDimension.objects.create(name="Ambiguous agency")
    tb1_batch = ImportBatch.objects.create(
        original_filename="tb1.xlsx",
        source_file="imports/tb1.xlsx",
        checksum_sha256="1" * 64,
        file_size=1,
    )
    tb2_batch = ImportBatch.objects.create(
        original_filename="tb2.xlsx",
        source_file="imports/tb2.xlsx",
        checksum_sha256="2" * 64,
        file_size=1,
    )
    tb1 = TB1RequestStagingRow.objects.create(
        batch=tb1_batch,
        agency=agency,
        sheet_name="JANVIER",
        source_row=2,
        row_hash="3" * 64,
    )
    first_tb2 = TB2SnapshotStagingRow.objects.create(
        batch=tb2_batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=2,
        row_hash="4" * 64,
    )
    second_tb2 = TB2SnapshotStagingRow.objects.create(
        batch=tb2_batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=3,
        row_hash="5" * 64,
    )

    _block_pair(
        tb1=tb1,
        tb2_rows=[first_tb2, second_tb2],
        code="ambiguous_match",
        message="More than one TB2 row has this match key.",
    )

    tb1.refresh_from_db()
    first_tb2.refresh_from_db()
    second_tb2.refresh_from_db()
    assert tb1.match_status == MatchStatus.BLOCKED
    assert first_tb2.match_status == MatchStatus.BLOCKED
    assert second_tb2.match_status == MatchStatus.BLOCKED
    assert DataQualityIssue.objects.filter(code="ambiguous_match").count() == 3


@pytest.mark.django_db
def test_credit_request_status_uses_the_frontend_label_field() -> None:
    status = StatusDimension.objects.create(
        code="awaiting_visit",
        name="En attente de visite",
        pipeline_stage=StatusDimension.PipelineStage.WAITING_VISIT,
    )

    assert CreditRequestStatusSummarySerializer(status).data["label"] == "En attente de visite"


@pytest.mark.django_db
def test_status_dimensions_can_be_seeded_from_service_definitions() -> None:
    seeded = ensure_status_dimensions()

    assert set(seeded) == set(STATUS_DEFINITIONS)
    assert StatusDimension.objects.filter(is_active=True).count() == len(STATUS_DEFINITIONS)
    assert seeded["funded"].name == "Décaissé"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    [
        CreditTypeDimension,
        RequestTypeDimension,
        ActivityDimension,
        RejectionReasonDimension,
    ],
)
def test_unknown_or_blank_governed_values_are_rejected(
    model: type[CreditTypeDimension]
    | type[RequestTypeDimension]
    | type[ActivityDimension]
    | type[RejectionReasonDimension],
) -> None:
    for raw_value in ("Unmapped source value", ""):
        with pytest.raises(WarehouseLoadError) as exc_info:
            _governed_dimension(
                raw_value=raw_value,
                target_model=model,
                field="dimension",
                issues=[],
            )

        assert exc_info.value.code == "unresolved_dimension_value"
        assert exc_info.value.field == "dimension"
    assert model.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("model", [CADimension, GPDimension])
@pytest.mark.parametrize("raw_value", ["Unmapped employee", ""])
def test_unknown_or_blank_staff_values_are_rejected(
    model: type[CADimension] | type[GPDimension], raw_value: str
) -> None:
    agency = AgencyDimension.objects.create(name="Fallback agency")

    with pytest.raises(WarehouseLoadError) as exc_info:
        _staff_dimension(
            agency=agency,
            raw_value=raw_value,
            dimension_model=model,
            field="staff",
        )

    assert exc_info.value.code in {"missing_employee_identity", "unresolved_employee_identity"}
    assert exc_info.value.field == "staff"
    assert model.objects.filter(agency=agency).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("model", [CADimension, GPDimension])
def test_staff_match_is_active_agency_scoped_and_accent_case_insensitive(
    model: type[CADimension] | type[GPDimension],
) -> None:
    agency = AgencyDimension.objects.create(name="Matching agency")
    other_agency = AgencyDimension.objects.create(name="Other agency")
    employee = model.objects.create(agency=agency, name="Élise Ben Salem")
    model.objects.create(agency=other_agency, name="Elise Ben Salem")

    resolved = _staff_dimension(
        agency=agency,
        raw_value="  elise ben salem ",
        dimension_model=model,
        field="staff",
    )

    assert resolved.pk == employee.pk
