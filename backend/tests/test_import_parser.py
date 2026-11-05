from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from apps.imports.parser import (
    AgencySource,
    CellValueError,
    InvalidWorkbookError,
    IssueSeverity,
    ParserConfigurationError,
    ParserLimits,
    UnsupportedWorkbookError,
    WorkbookKind,
    WorkbookLimitError,
    coerce_date,
    coerce_decimal,
    infer_agency_from_filename,
    infer_reporting_period,
    normalize_header,
    parse_workbook,
)

TB1_HEADERS = (
    "Référence de la demande",
    "Nom du client",
    "Numéro Tél du client",
    "Adresse",
    "Date de la demande",
    "Type de demande",
    "Montant demandé",
    "Type de crédit",
    "Catégorie d\u2019activité",
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
    "Date réception Chef d\u2019agence",
    "Nom du conseiller CA/CAA",
    "Date d\u2019affectation au GP",
    "Nom du GP",
    "DATE VISITE CLIENT",
    "STATUT/ETAT DEMANDE",
    "DATE DECAISSEMENT / DATE REJET",
    "Motif du rejet",
    "Commentaires",
)


def workbook_bytes(workbook: Workbook) -> BytesIO:
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def active_sheet(workbook: Workbook) -> Worksheet:
    sheet = workbook.active
    assert isinstance(sheet, Worksheet)
    return sheet


def build_tb1_workbook() -> Workbook:
    workbook = Workbook()
    sheet = active_sheet(workbook)
    sheet.title = "JANVIER 2026"
    sheet.append(["Synthetic import title"])
    sheet.append([])
    sheet.append(TB1_HEADERS)
    sheet.append(
        [
            "1200/001/P/15012026",
            "Synthetic Client",
            "00000000",
            "Synthetic address",
            "15/01/2026",
            "NOUVEAU",
            "1 234,50 TND",
            "Synthetic commerce",
            "Commerce",
        ]
    )
    return workbook


def build_tb2_workbook() -> Workbook:
    workbook = Workbook()
    sheet = active_sheet(workbook)
    sheet.title = "SYNTHETIC EAST"
    sheet.append(TB2_HEADERS)
    sheet.append(
        [
            None,
            "1200/002/P/28042026",
            datetime(2026, 4, 28, 8, 30),
            "Synthetic Client Two",
            "1200",
            "00000000",
            "Synthetic address two",
            "REN",
            2500,
            "29/04/2026",
            "Synthetic CA",
            date(2026, 4, 30),
            "Synthetic GP",
            "02/05/2026",
            "Décaissé",
            "05/05/2026",
            None,
            "Synthetic comment",
        ]
    )
    return workbook


def test_parse_tb1_with_override_lineage_profile_and_blank_stop() -> None:
    workbook = build_tb1_workbook()
    sheet = active_sheet(workbook)
    sheet.append([])
    sheet.append([])
    sheet.append(
        [
            "SYN-SHOULD-NOT-BE-PARSED",
            "Synthetic Late Row",
            "00000001",
            1,
            "Synthetic service",
            "Synthetic address",
            "16/01/2026",
            "NOUVEAU",
        ]
    )

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="SUIVI ACCEUIL AGENCE TESTVILLE 2026_uniformise.xlsx",
        limits=ParserLimits(consecutive_blank_rows=2),
    )

    assert result.metadata.kind is WorkbookKind.TB1
    assert result.metadata.agency == "TESTVILLE"
    assert result.metadata.reporting_period == date(2026, 1, 1)
    assert result.metadata.source_sheet_count == 1
    assert result.metadata.parsed_sheet_count == 1
    assert len(result.rows) == 1

    sheet_result = result.sheets[0]
    assert sheet_result.metadata.header_row == 3
    assert sheet_result.metadata.columns_scanned == 9
    assert sheet_result.metadata.blank_terminated is True
    row = result.rows[0]
    assert row.sheet_name == "JANVIER 2026"
    assert row.source_row == 4
    assert row.agency == "TESTVILLE"
    assert row.agency_source is AgencySource.FILENAME
    assert row.reporting_period == date(2026, 1, 1)
    assert row.data["reference"] == "1200/001/P/15012026"
    assert "phone" not in row.data
    assert "NOM CLIENT" not in row.raw_data
    assert row.data["amount"] == Decimal("1234.50")
    assert row.data["request_date"] == date(2026, 1, 15)
    assert row.is_valid is True
    json.dumps(row.raw_data, allow_nan=False)

    assert result.profile.row_count == 1
    assert result.profile.valid_row_count == 1
    assert result.profile.invalid_row_count == 0
    assert result.profile.agency_count == 1
    assert result.profile.period_count == 1
    assert result.profile.schema_valid is True


def test_parse_tb2_infers_snapshot_period_and_sheet_agency() -> None:
    result = parse_workbook(
        workbook_bytes(build_tb2_workbook()),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    assert result.metadata.kind is WorkbookKind.TB2
    assert result.metadata.reporting_period == date(2026, 5, 1)
    assert result.metadata.agency == "SYNTHETIC EAST"
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.agency == "SYNTHETIC EAST"
    assert row.agency_source is AgencySource.SHEET
    assert row.reporting_period == date(2026, 5, 1)
    assert "phone" not in row.data
    assert row.data["amount"] == Decimal("2500")
    assert row.data["request_date"] == date(2026, 4, 28)
    assert row.data["received_at_agency_date"] == date(2026, 4, 29)
    assert row.data["assigned_to_gp_date"] == date(2026, 4, 30)
    assert row.data["visit_date"] == date(2026, 5, 2)
    assert row.data["outcome_date"] == date(2026, 5, 5)
    assert row.raw_data["Date de la demande"] == "2026-04-28T08:30:00"
    assert result.profile.schema_valid is True


def test_tb2_derives_rejection_from_terminal_date_and_status() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    sheet.cell(row=2, column=headers.index("STATUT/ETAT DEMANDE") + 1).value = "REJETÉ"
    sheet.cell(row=2, column=headers.index("Motif du rejet") + 1).value = "Dossier incomplet"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.is_valid is True
    assert row.data["rejection_date"] == date(2026, 5, 5)


@pytest.mark.parametrize("status", ["Décaissé", "Rejeté"])
def test_tb2_terminal_status_requires_terminal_date(status: str) -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    sheet.cell(row=2, column=headers.index("STATUT/ETAT DEMANDE") + 1).value = status
    sheet.cell(row=2, column=headers.index("DATE DECAISSEMENT / DATE REJET") + 1).value = None
    if status == "Rejeté":
        sheet.cell(row=2, column=headers.index("Motif du rejet") + 1).value = "Dossier incomplet"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.is_valid is False
    assert any(issue.code == "terminal_status_requires_terminal_date" for issue in row.issues)


def test_tb2_rejected_status_requires_rejection_reason() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    sheet.cell(row=2, column=headers.index("STATUT/ETAT DEMANDE") + 1).value = "Rejeté"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.is_valid is False
    assert any(issue.code == "rejected_status_requires_rejection_reason" for issue in row.issues)


def test_tb2_registered_request_does_not_require_ca_or_gp() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    for header in (
        "Date réception Chef d\u2019agence",
        "Nom du conseiller CA/CAA",
        "Date d\u2019affectation au GP",
        "Nom du GP",
        "DATE VISITE CLIENT",
        "DATE DECAISSEMENT / DATE REJET",
        "Motif du rejet",
    ):
        sheet.cell(row=2, column=headers.index(header) + 1).value = None
    sheet.cell(row=2, column=headers.index("STATUT/ETAT DEMANDE") + 1).value = "Demande enregistrée"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    assert result.rows[0].is_valid is True


def test_tb2_lifecycle_requires_employee_identity_and_prior_milestones() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    sheet.cell(row=2, column=headers.index("Nom du conseiller CA/CAA") + 1).value = None
    sheet.cell(row=2, column=headers.index("Date réception Chef d\u2019agence") + 1).value = None

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    codes = {issue.code for issue in result.rows[0].issues}
    assert "assignment_requires_reception" in codes

    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    sheet.cell(row=2, column=headers.index("Nom du conseiller CA/CAA") + 1).value = None
    sheet.cell(row=2, column=headers.index("Date d\u2019affectation au GP") + 1).value = None
    sheet.cell(row=2, column=headers.index("Nom du GP") + 1).value = None
    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    codes = {issue.code for issue in result.rows[0].issues}
    assert {"missing_counsellor_name", "visit_requires_gp_assignment"} <= codes


def test_tb2_terminal_date_requires_decaissed_or_rejected_status() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    headers = [cell.value for cell in sheet[1]]
    sheet.cell(row=2, column=headers.index("STATUT/ETAT DEMANDE") + 1).value = "Financé"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    assert any(
        issue.code == "terminal_date_requires_terminal_status" for issue in result.rows[0].issues
    )


def test_tb2_sheet_identity_wins_over_a_conflicting_agency_cell() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    sheet["A2"] = "Synthetic conflicting agency cell"

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.agency == "SYNTHETIC EAST"
    assert row.agency_source is AgencySource.SHEET
    assert any(issue.code == "agency_cell_conflicts_with_source" for issue in row.issues)
    assert row.is_valid is False


def test_invalid_values_are_quarantined_without_echoing_cell_contents() -> None:
    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    sheet.delete_rows(2)
    sheet.append(
        [
            "SYNTHETIC EAST",
            None,
            "not-a-date-secret",
            "Synthetic Invalid Client",
            "SYN-CUSTOMER",
            "00000000",
            "Synthetic address",
            "NV",
            "not-an-amount-secret",
            None,
            None,
            None,
            None,
            None,
            None,
            "EN COURS",
            None,
            None,
            None,
        ]
    )

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.is_valid is False
    assert result.profile.invalid_row_count == 1
    codes = {issue.code for issue in row.issues}
    assert {"invalid_date", "invalid_decimal", "missing_required_value"} <= codes
    issue_report = " ".join(issue.message for issue in row.issues)
    assert "not-a-date-secret" not in issue_report
    assert "not-an-amount-secret" not in issue_report
    assert all(issue.severity is IssueSeverity.ERROR for issue in row.issues)


def test_negative_amount_is_quarantined_without_rejecting_the_batch_schema() -> None:
    workbook = build_tb1_workbook()
    active_sheet(workbook)["G4"] = -5

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="SUIVI ACCEUIL SYNTHETIC 2026.xlsx",
    )

    assert any(issue.code == "negative_amount" for issue in result.rows[0].issues)
    assert result.profile.schema_valid is True
    assert not any(issue.code == "batch_schema_validation_failed" for issue in result.issues)


@pytest.mark.parametrize(
    ("cell", "field"),
    [
        ("F4", "request_type"),
        ("H4", "credit_type"),
        ("I4", "activity_category"),
    ],
)
def test_tb1_governed_dimension_values_are_mandatory(cell: str, field: str) -> None:
    workbook = build_tb1_workbook()
    active_sheet(workbook)[cell] = None

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="SUIVI ACCEUIL SYNTHETIC 2026.xlsx",
    )

    issues = [issue for issue in result.rows[0].issues if issue.field == field]
    assert any(issue.code == "missing_required_value" for issue in issues)
    assert result.rows[0].is_valid is False


@pytest.mark.parametrize(
    ("cell", "value", "field"),
    [
        ("I2", Decimal("1000000000000000"), "amount"),
    ],
)
def test_out_of_range_decimals_are_sanitized_row_errors(
    cell: str, value: Decimal, field: str
) -> None:
    workbook = build_tb2_workbook()
    active_sheet(workbook)[cell] = value

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="Etat des en cours agences 05-26.xlsx",
    )

    row = result.rows[0]
    assert row.is_valid is False
    assert row.data[field] is None
    assert any(
        issue.code == "invalid_decimal"
        and issue.field == field
        and issue.severity is IssueSeverity.ERROR
        for issue in row.issues
    )
    assert str(value) not in " ".join(issue.message for issue in row.issues)


def test_corrupt_reported_dimensions_are_not_trusted() -> None:
    workbook = build_tb1_workbook()
    far_cell = active_sheet(workbook).cell(row=1_048_576, column=16_384)
    far_cell.fill = PatternFill(fill_type="solid", fgColor="FFFFFF")

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="SUIVI ACCEUIL SYNTHETIC 2026.xlsx",
        limits=ParserLimits(consecutive_blank_rows=2),
    )

    assert len(result.rows) == 1
    assert result.sheets[0].metadata.columns_scanned == 9
    assert result.sheets[0].metadata.last_scanned_row == 6
    assert result.sheets[0].metadata.blank_terminated is True


def test_safe_limits_and_unsupported_files_have_stable_exception_types() -> None:
    with pytest.raises(InvalidWorkbookError, match="readable XLSX"):
        parse_workbook(BytesIO(b"not an xlsx"), source_name="synthetic.xlsx")

    empty_workbook = Workbook()
    with pytest.raises(UnsupportedWorkbookError, match="No supported"):
        parse_workbook(workbook_bytes(empty_workbook), source_name="synthetic.xlsx")

    workbook_with_two_sheets = build_tb1_workbook()
    workbook_with_two_sheets.create_sheet("FEVRIER 2026")
    with pytest.raises(WorkbookLimitError, match="sheet limit"):
        parse_workbook(
            workbook_bytes(workbook_with_two_sheets),
            source_name="SUIVI ACCEUIL SYNTHETIC 2026.xlsx",
            limits=ParserLimits(max_sheets=1),
        )

    row_limited_workbook = build_tb1_workbook()
    active_sheet(row_limited_workbook).append(
        [
            "SYN-003",
            "Synthetic Client Three",
            "00000003",
            3,
            "Synthetic credit",
            "Synthetic address",
            "17/01/2026",
            "NOUVEAU",
        ]
    )
    with pytest.raises(WorkbookLimitError, match="row-scan limit"):
        parse_workbook(
            workbook_bytes(row_limited_workbook),
            source_name="SUIVI ACCEUIL SYNTHETIC 2026.xlsx",
            limits=ParserLimits(max_rows_per_sheet=1),
        )


def test_header_overrides_are_rejected_and_limit_configuration_is_validated() -> None:
    with pytest.raises(ParserConfigurationError, match="not permitted"):
        parse_workbook(
            workbook_bytes(build_tb1_workbook()),
            header_overrides={"Téléphone mobile": "surprise_field"},
        )
    with pytest.raises(ParserConfigurationError, match="positive"):
        ParserLimits(max_columns=0)
    with pytest.raises(ParserConfigurationError, match="column limit"):
        ParserLimits(max_columns=16_385)


def test_governed_template_headers_are_exact_but_order_independent() -> None:
    workbook = build_tb1_workbook()
    sheet = active_sheet(workbook)
    headers = list(TB1_HEADERS)
    values = list(next(sheet.iter_rows(min_row=2, max_row=2, values_only=True)))
    reordered = list(reversed(range(len(headers))))
    sheet.delete_rows(1, 2)
    sheet.append([headers[index] for index in reordered])
    sheet.append([values[index] for index in reordered])

    result = parse_workbook(
        workbook_bytes(workbook),
        source_name="SUIVI ACCUEIL TESTVILLE.xlsx",
    )

    assert result.rows[0].is_valid is True
    assert result.rows[0].data["reference"] == "1200/001/P/15012026"


def test_historical_or_incomplete_headers_are_rejected() -> None:
    workbook = build_tb1_workbook()
    sheet = active_sheet(workbook)
    sheet["A3"] = "REFERENCE DEMANDE"
    with pytest.raises(UnsupportedWorkbookError, match="No supported"):
        parse_workbook(workbook_bytes(workbook), source_name="SUIVI ACCUEIL TESTVILLE.xlsx")

    workbook = build_tb2_workbook()
    sheet = active_sheet(workbook)
    sheet.delete_cols(1)
    with pytest.raises(UnsupportedWorkbookError, match="No supported"):
        parse_workbook(
            workbook_bytes(workbook),
            source_name="Etat des en cours agences 05-26.xlsx",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 234,50 TND", Decimal("1234.50")),
        ("1.234,50", Decimal("1234.50")),
        ("1,234.50", Decimal("1234.50")),
        ("1.234", Decimal("1234")),
        (2500, Decimal("2500")),
        (12.5, Decimal("12.5")),
        (None, None),
    ],
)
def test_decimal_coercion(raw: object, expected: Decimal | None) -> None:
    assert coerce_decimal(raw) == expected


@pytest.mark.parametrize("raw", [True, "not-a-number", float("inf")])
def test_invalid_decimal_coercion(raw: object) -> None:
    with pytest.raises(CellValueError):
        coerce_decimal(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (date(2026, 1, 2), date(2026, 1, 2)),
        (datetime(2026, 1, 2, 9, 30), date(2026, 1, 2)),
        ("02/01/2026", date(2026, 1, 2)),
        ("2026-01-02", date(2026, 1, 2)),
        ("2 février 2026", date(2026, 2, 2)),
        (None, None),
    ],
)
def test_date_coercion(raw: object, expected: date | None) -> None:
    assert coerce_date(raw) == expected


@pytest.mark.parametrize("raw", [False, "31/02/2026", "secret-not-a-date"])
def test_invalid_date_coercion(raw: object) -> None:
    with pytest.raises(CellValueError):
        coerce_date(raw)


def test_label_inference_normalizes_french_accents_and_filename_variants() -> None:
    assert normalize_header("  DÉLAIS ACC\u2013CA ") == "delais acc ca"
    assert infer_reporting_period("Etat des en cours agences 04-26.xlsx") == date(2026, 4, 1)
    assert infer_reporting_period("FÉVRIER 2026") == date(2026, 2, 1)
    assert (
        infer_agency_from_filename("SUIVI ACCEUIL AGENCE SYNTHETIC NORTH 2026_uniformise.xlsx")
        == "SYNTHETIC NORTH"
    )
