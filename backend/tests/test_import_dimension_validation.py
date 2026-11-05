from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.db import IntegrityError
from openpyxl import Workbook

from apps.data_quality.models import DataQualityIssue
from apps.imports.models import (
    ImportBatch,
    MatchStatus,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
    ValidationStatus,
)
from apps.imports.parser import AgencySource, ParsedRow, WorkbookKind
from apps.imports.services import (
    _employee_identity_issues,
    _governed_dimension_issues,
    _governed_reference_issues,
    _mark_absent_from_latest_tb2,
    _publish_pair,
    process_batch,
)
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CreditTypeDimension,
    FactCreditRequest,
    GPDimension,
    RequestTypeDimension,
)


@pytest.mark.django_db
def test_tb1_unknown_or_inactive_dimension_values_are_row_errors() -> None:
    CreditTypeDimension.objects.create(name="Microcrédit", is_active=True)
    ActivityDimension.objects.create(name="Commerce", is_active=False)
    RequestTypeDimension.objects.create(name="Nouvelle demande", is_active=True)
    parsed_row = ParsedRow(
        sheet_name="Avril 2026",
        source_row=8,
        agency="ARIANA",
        agency_source=AgencySource.FILENAME,
        reporting_period=date(2026, 4, 1),
        data={},
        raw_data={},
        issues=(),
    )

    issues = _governed_dimension_issues(
        data={
            "credit_type": "microcredit",
            "activity_category": "Commerce",
            "request_type": "Valeur inventée",
        },
        source_kind=WorkbookKind.TB1,
        parsed_row=parsed_row,
    )

    assert {issue.field for issue in issues} == {"activity_category", "request_type"}
    assert all(issue.code == "unresolved_dimension_value" for issue in issues)


@pytest.mark.django_db
def test_tb1_dimension_matching_ignores_case_and_accents() -> None:
    CreditTypeDimension.objects.create(name="Microcrédit")
    ActivityDimension.objects.create(name="Activité artisanale")
    RequestTypeDimension.objects.create(name="Nouvelle demande")
    parsed_row = ParsedRow(
        sheet_name="Avril 2026",
        source_row=8,
        agency="ARIANA",
        agency_source=AgencySource.FILENAME,
        reporting_period=date(2026, 4, 1),
        data={},
        raw_data={},
        issues=(),
    )

    issues = _governed_dimension_issues(
        data={
            "credit_type": "MICROCREDIT",
            "activity_category": "activite artisanale",
            "request_type": "NOUVELLE DEMANDE",
        },
        source_kind=WorkbookKind.TB1,
        parsed_row=parsed_row,
    )

    assert issues == ()


@pytest.mark.django_db
def test_dimension_activation_lifecycle_controls_new_import_validation() -> None:
    credit_type = CreditTypeDimension.objects.create(name="Crédit saisonnier", is_active=True)
    activity = ActivityDimension.objects.create(name="Commerce", is_active=True)
    request_type = RequestTypeDimension.objects.create(name="Nouvelle demande", is_active=True)
    parsed_row = ParsedRow(
        sheet_name="Avril 2026",
        source_row=8,
        agency="ARIANA",
        agency_source=AgencySource.FILENAME,
        reporting_period=date(2026, 4, 1),
        data={},
        raw_data={},
        issues=(),
    )
    values = {
        "credit_type": credit_type.name,
        "activity_category": activity.name,
        "request_type": request_type.name,
    }

    assert (
        _governed_dimension_issues(data=values, source_kind=WorkbookKind.TB1, parsed_row=parsed_row)
        == ()
    )
    credit_type.is_active = False
    credit_type.save(update_fields=["is_active"])
    issues = _governed_dimension_issues(
        data=values, source_kind=WorkbookKind.TB1, parsed_row=parsed_row
    )
    assert [(issue.code, issue.field) for issue in issues] == [
        ("unresolved_dimension_value", "credit_type")
    ]
    credit_type.is_active = True
    credit_type.save(update_fields=["is_active"])
    assert (
        _governed_dimension_issues(data=values, source_kind=WorkbookKind.TB1, parsed_row=parsed_row)
        == ()
    )


@pytest.mark.django_db
def test_agency_code_change_preserves_old_reference_and_governs_new_imports() -> None:
    agency = AgencyDimension.objects.create(name="ARIANA", code="1200")
    fact = FactCreditRequest.objects.create(agency=agency, reference="1200/001/P/15042026")
    parsed_row = ParsedRow(
        sheet_name="Avril 2026",
        source_row=8,
        agency="ARIANA",
        agency_source=AgencySource.FILENAME,
        reporting_period=date(2026, 4, 1),
        data={},
        raw_data={},
        issues=(),
    )
    agency.code = "9999"
    agency.save(update_fields=["code"])

    assert FactCreditRequest.objects.get(reference=fact.reference).reference == fact.reference
    old_issues = _governed_reference_issues(
        agency=agency,
        data={"reference": "1200/001/P/15042026"},
        parsed_row=parsed_row,
    )
    new_issues = _governed_reference_issues(
        agency=agency,
        data={"reference": "9999/001/P/15042026"},
        parsed_row=parsed_row,
    )
    assert [issue.code for issue in old_issues] == ["reference_agency_code_mismatch"]
    assert new_issues == ()


@pytest.mark.django_db
def test_moved_gp_only_resolves_for_its_new_agency() -> None:
    ariana = AgencyDimension.objects.create(name="ARIANA", code="1200")
    tunis = AgencyDimension.objects.create(name="TUNIS", code="1300")
    gp = GPDimension.objects.create(name="Karim Trabelsi", agency=ariana)
    parsed_row = ParsedRow(
        sheet_name="ARIANA",
        source_row=8,
        agency="ARIANA",
        agency_source=AgencySource.SHEET,
        reporting_period=date(2026, 4, 1),
        data={},
        raw_data={},
        issues=(),
    )
    data = {"assigned_to_gp_date": date(2026, 4, 16), "gp_name": gp.name}

    assert _employee_identity_issues(agency=ariana, data=data, parsed_row=parsed_row) == ()
    gp.agency = tunis
    gp.save(update_fields=["agency"])
    issues = _employee_identity_issues(agency=ariana, data=data, parsed_row=parsed_row)
    assert [issue.code for issue in issues] == ["unresolved_employee_identity"]
    assert _employee_identity_issues(agency=tunis, data=data, parsed_row=parsed_row) == ()


@pytest.mark.django_db
def test_process_batch_rejects_entire_workbook_and_retains_only_safe_row_values() -> None:
    AgencyDimension.objects.create(name="ARIANA", code="1200")
    CreditTypeDimension.objects.create(name="Microcrédit")
    ActivityDimension.objects.create(name="Commerce")
    RequestTypeDimension.objects.create(name="Nouvelle demande")
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Avril 2026"
    worksheet.append(
        [
            "Référence de la demande",
            "Date de la demande",
            "Type de demande",
            "Montant demandé",
            "Type de crédit",
            "Catégorie d\u2019activité",
        ]
    )
    worksheet.append(
        ["1200/001/P/15042026", "15/04/2026", "Nouvelle demande", 15000, "Inventé", "Commerce"]
    )
    stream = BytesIO()
    workbook.save(stream)
    batch = ImportBatch(
        original_filename="SUIVI ACCUEIL ARIANA.xlsx",
        checksum_sha256="9" * 64,
        file_size=len(stream.getvalue()),
    )
    batch.source_file.save("dimension-validation.xlsx", ContentFile(stream.getvalue()), save=False)
    batch.save()

    result = process_batch(str(batch.pk))

    batch.refresh_from_db()
    issue = DataQualityIssue.objects.get(batch=batch, field_name="credit_type")
    assert result["status"] == ImportBatch.Status.FAILED
    assert batch.status == ImportBatch.Status.FAILED
    assert not TB1RequestStagingRow.objects.filter(batch=batch).exists()
    assert not FactCreditRequest.objects.exists()
    assert not batch.source_file.name
    assert issue.code == "unresolved_dimension_value"
    assert issue.details["row_values"] == {
        "reference": "1200/001/P/15042026",
        "request_date": "15/04/2026",
        "request_type": "Nouvelle demande",
        "amount": 15000,
        "credit_type": "Inventé",
        "activity_category": "Commerce",
    }
    assert issue.details["row_values"]["reference"] == "1200/001/P/15042026"


@pytest.mark.django_db
def test_latest_tb2_submission_flags_only_dossiers_absent_from_that_month() -> None:
    agency = AgencyDimension.objects.create(name="ARIANA", code="1200")
    july_batch = ImportBatch.objects.create(
        original_filename="SUIVI ENCOURS JUILLET.xlsx",
        checksum_sha256="a" * 64,
        file_size=1,
        workbook_type=ImportBatch.WorkbookType.TB2,
        status=ImportBatch.Status.COMPLETED,
        reporting_period=date(2026, 7, 1),
    )
    old_present = TB2SnapshotStagingRow.objects.create(
        batch=july_batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=2,
        reporting_period=date(2026, 7, 1),
        reference="1200/001/P/01072026",
        validation_status=ValidationStatus.VALID,
    )
    old_missing = TB2SnapshotStagingRow.objects.create(
        batch=july_batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=3,
        reporting_period=date(2026, 7, 1),
        reference="1200/002/P/01072026",
        validation_status=ValidationStatus.VALID,
    )
    present_fact = FactCreditRequest.objects.create(
        agency=agency,
        reference=old_present.reference,
        current_tb2_row=old_present,
    )
    missing_fact = FactCreditRequest.objects.create(
        agency=agency,
        reference=old_missing.reference,
        current_tb2_row=old_missing,
    )
    august_batch = ImportBatch.objects.create(
        original_filename="SUIVI ENCOURS AOUT.xlsx",
        checksum_sha256="b" * 64,
        file_size=1,
        workbook_type=ImportBatch.WorkbookType.TB2,
        status=ImportBatch.Status.PROCESSING,
        reporting_period=date(2026, 8, 1),
    )
    TB2SnapshotStagingRow.objects.create(
        batch=august_batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=2,
        reporting_period=date(2026, 8, 1),
        reference=present_fact.reference,
        validation_status=ValidationStatus.VALID,
    )

    _mark_absent_from_latest_tb2(batch=august_batch)

    present_fact.refresh_from_db()
    missing_fact.refresh_from_db()
    assert present_fact.missing_from_latest_tb2_period is None
    assert missing_fact.missing_from_latest_tb2_period == date(2026, 8, 1)


@pytest.mark.django_db
def test_pair_publication_retries_a_concurrent_fact_insert() -> None:
    agency = AgencyDimension.objects.create(name="ARIANA", code="1200")
    batch = ImportBatch.objects.create(
        original_filename="SUIVI ACCUEIL ARIANA.xlsx",
        checksum_sha256="c" * 64,
        file_size=1,
        status=ImportBatch.Status.PROCESSING,
    )
    tb1 = TB1RequestStagingRow.objects.create(
        batch=batch,
        agency=agency,
        sheet_name="Avril 2026",
        source_row=2,
        reference="1200/001/P/01042026",
        validation_status=ValidationStatus.VALID,
    )
    tb2 = TB2SnapshotStagingRow.objects.create(
        batch=batch,
        agency=agency,
        sheet_name="ARIANA",
        source_row=2,
        reference=tb1.reference,
        validation_status=ValidationStatus.VALID,
    )
    result = SimpleNamespace(issues=())

    with patch(
        "apps.imports.services.load_credit_request",
        side_effect=[IntegrityError("duplicate fact"), result, result],
    ) as load:
        assert _publish_pair(tb1=tb1, tb2=tb2) is True

    assert load.call_count == 3
    tb1.refresh_from_db()
    tb2.refresh_from_db()
    assert tb1.match_status == MatchStatus.MATCHED
    assert tb2.match_status == MatchStatus.MATCHED
