from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook

from apps.imports.models import (
    ImportBatch,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
    ValidationStatus,
)
from apps.imports.parser import WorkbookKind, parse_workbook
from apps.imports.serializers import DataQualityIssueSerializer
from apps.imports.services import _supersede_prior_scopes
from apps.warehouse.models import AgencyDimension

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPOSITORY_ROOT / "templates"

TB1_HEADERS = (
    "Référence de la demande",
    "Nom du client",
    "Numéro Tél du client",
    "Adresse",
    "Date de la demande",
    "Type de demande",
    "Montant demandé",
    "Type de crédit",
    "Catégorie d’activité",
)
TB2_HEADERS = (
    "AGENCE",
    "Référence de la demande",
    "Date de la demande",
    "Nom du client",
    "Numéro client",
    "Numéro Tél du client",
    "Adresse",
    "Type de demande",
    "Montant demandé",
    "Date réception Chef d’agence",
    "Nom du conseiller CA/CAA",
    "Date d’affectation au GP",
    "Nom du GP",
    "DATE VISITE CLIENT",
    "STATUT/ETAT DEMANDE",
    "DATE DECAISSEMENT / DATE REJET",
    "Motif du rejet",
    "Commentaires",
)
TB2_AGENCIES = (
    "ARIANA",
    "BEJA",
    "BEN AROUS",
    "BIZERTE",
    "DJERBA",
    "EZZAHROUNI",
    "FAHS",
    "GABES",
    "GAFSA",
    "JENDOUBA",
    "KASSERINE",
    "KEF",
    "MAHDIA",
    "NABEUL",
    "SFAX",
    "SIDI BOUZID",
    "SILIANA",
    "SOUSSE",
    "TCV",
    "TOZEUR",
)


def _headers(worksheet: object) -> tuple[object, ...]:
    return tuple(cell.value for cell in worksheet[1])  # type: ignore[index]


def test_versioned_tb1_template_is_the_authoritative_month_sheet_layout() -> None:
    path = TEMPLATES_DIR / "SUIVI ACCUEIL <NOM DE L’AGENCE>.xlsx"
    workbook = load_workbook(path, read_only=True)

    assert workbook.sheetnames == ["<Mois> <Année>"]
    worksheet = workbook.active
    assert worksheet is not None
    assert _headers(worksheet) == TB1_HEADERS
    assert all(
        all(value is None for value in row)
        for row in worksheet.iter_rows(min_row=2, values_only=True)
    )
    parsed = parse_workbook(path)
    assert parsed.metadata.kind is WorkbookKind.TB1
    assert parsed.metadata.parsed_sheet_count == 1


def test_tb1_month_sheet_name_drives_the_reporting_period(tmp_path: Path) -> None:
    source = TEMPLATES_DIR / "SUIVI ACCUEIL <NOM DE L’AGENCE>.xlsx"
    target = tmp_path / "SUIVI ACCUEIL ARIANA.xlsx"
    workbook = load_workbook(source)
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Avril 2026"
    worksheet.append(
        (
            "TB1-APR-001",
            "Client confidentiel",
            "20 000 000",
            "Adresse confidentielle",
            "15/04/2026",
            "Nouvelle demande",
            1_000,
            "ACV",
            "Commerce",
        )
    )
    workbook.save(target)

    parsed = parse_workbook(target)

    assert parsed.rows[0].reporting_period == date(2026, 4, 1)


def test_versioned_tb2_template_is_the_authoritative_multi_agency_layout() -> None:
    path = TEMPLATES_DIR / "Etat des en cours agences <MM-YY>.xlsx"
    workbook = load_workbook(path, read_only=True)

    assert tuple(workbook.sheetnames) == TB2_AGENCIES
    assert all(_headers(workbook[name]) == TB2_HEADERS for name in TB2_AGENCIES)
    assert all(
        all(value is None for value in row)
        for worksheet in workbook
        for row in worksheet.iter_rows(min_row=2, values_only=True)
    )
    parsed = parse_workbook(path)
    assert parsed.metadata.kind is WorkbookKind.TB2
    assert parsed.metadata.parsed_sheet_count == len(TB2_AGENCIES)


def test_template_sensitive_columns_are_never_retained_or_reported(tmp_path: Path) -> None:
    source = TEMPLATES_DIR / "Etat des en cours agences <MM-YY>.xlsx"
    target = tmp_path / "Etat des en cours agences 04-26.xlsx"
    workbook = load_workbook(source)
    worksheet = workbook["ARIANA"]
    row_values: tuple[str | int, ...] = (
        "ARIANA",
        "TB2-APR-001",
        "01/04/2026",
        "Client confidentiel",
        "ID-CLIENT-CONFIDENTIEL",
        "20 000 000",
        "Adresse confidentielle",
        "Nouvelle demande",
        1_000,
        "02/04/2026",
        "",
        "",
        "",
        "",
        "En attente d'affectation GP",
        "",
        "",
        "Commentaire confidentiel",
    )
    for column_number, value in enumerate(row_values, start=1):
        worksheet.cell(row=2, column=column_number, value=value)
    workbook.save(target)

    parsed = parse_workbook(target)
    row = next(row for row in parsed.rows if row.sheet_name == "ARIANA")
    protected_values = {
        "Client confidentiel",
        "ID-CLIENT-CONFIDENTIEL",
        "20 000 000",
        "Adresse confidentielle",
        "Commentaire confidentiel",
    }
    retained = json.dumps({"data": row.data, "raw_data": row.raw_data}, default=str)
    report_content = json.dumps(
        [issue.message for issue in (*parsed.issues, *row.issues)],
        ensure_ascii=False,
    )

    assert not any(value in retained for value in protected_values)
    assert not any(value in report_content for value in protected_values)
    assert not {
        "client_name",
        "client_identifier",
        "phone",
        "address",
        "comments",
        "raw_data",
        "details",
    } & set(DataQualityIssueSerializer.Meta.fields)
    persisted_fields = {
        field.name
        for model in (TB1RequestStagingRow, TB2SnapshotStagingRow)
        for field in model._meta.fields
    }
    assert (
        not {"client_name", "client_identifier", "phone", "address", "comments"} & persisted_fields
    )


@pytest.mark.django_db
def test_consolidated_tb2_supersession_is_scoped_to_agency_and_period() -> None:
    ariana = AgencyDimension.objects.create(name="ARIANA")
    beja = AgencyDimension.objects.create(name="BEJA")
    old_batch = ImportBatch.objects.create(
        checksum_sha256="a" * 64,
        file_size=1,
        status=ImportBatch.Status.COMPLETED,
        workbook_type=ImportBatch.WorkbookType.TB2,
    )
    new_batch = ImportBatch.objects.create(
        checksum_sha256="b" * 64,
        file_size=1,
        status=ImportBatch.Status.PROCESSING,
        workbook_type=ImportBatch.WorkbookType.TB2,
    )
    old_ariana = TB2SnapshotStagingRow.objects.create(
        batch=old_batch,
        agency=ariana,
        reporting_period=date(2026, 4, 1),
        sheet_name="ARIANA",
        source_row=2,
        row_hash="1" * 64,
    )
    old_beja = TB2SnapshotStagingRow.objects.create(
        batch=old_batch,
        agency=beja,
        reporting_period=date(2026, 4, 1),
        sheet_name="BEJA",
        source_row=2,
        row_hash="2" * 64,
    )
    TB2SnapshotStagingRow.objects.create(
        batch=new_batch,
        agency=ariana,
        reporting_period=date(2026, 4, 1),
        sheet_name="ARIANA",
        source_row=2,
        row_hash="3" * 64,
        validation_status=ValidationStatus.VALID,
    )

    _supersede_prior_scopes(batch=new_batch)

    old_ariana.refresh_from_db()
    old_beja.refresh_from_db()
    old_batch.refresh_from_db()
    assert old_ariana.is_current is False
    assert old_beja.is_current is True
    assert old_batch.status == ImportBatch.Status.COMPLETED
