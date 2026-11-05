import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import ImportBatch, TB2SnapshotStagingRow


@pytest.mark.django_db
def test_issue_report_exposes_only_whitelisted_correction_values() -> None:
    user = User.objects.create_user(username="quality-operator", password="secure-test-password")
    client = APIClient()
    client.force_authenticate(user=user)
    batch = ImportBatch.objects.create(
        original_filename="Etat des en cours agences 08-26.xlsx",
        source_file="",
        checksum_sha256="a" * 64,
        file_size=1,
    )
    row = TB2SnapshotStagingRow.objects.create(
        batch=batch,
        sheet_name="ARIANA",
        source_row=18,
        row_hash="b" * 64,
        ca_name="Conseiller inconnu",
        correction_values={
            "agency": "ARIANA",
            "amount": "15000",
            "counsellor_name": "Conseiller inconnu",
            "reference": "must-not-be-returned",
        },
    )
    DataQualityIssue.objects.create(
        batch=batch,
        tb2_row=row,
        severity=DataQualityIssue.Severity.ERROR,
        code="unresolved_employee_identity",
        field_name="counsellor_name",
        message="The CA/CAA name must match an active employee in the agency.",
    )
    DataQualityIssue.objects.create(
        batch=batch,
        tb2_row=row,
        severity=DataQualityIssue.Severity.ERROR,
        code="missing_match_key",
        field_name="reference",
        message="The row has no safe match key.",
        details={"submitted_value": "must-not-be-returned"},
    )
    DataQualityIssue.objects.create(
        batch=batch,
        tb2_row=row,
        severity=DataQualityIssue.Severity.ERROR,
        code="missing_required_value",
        field_name="credit_type",
        message="The required field credit_type is blank.",
        details={"submitted_value": ""},
    )

    issues_response = client.get(reverse("imports:import-batch-issues", kwargs={"pk": batch.pk}))
    assert issues_response.status_code == 200
    issues = {issue["code"]: issue for issue in issues_response.json()["results"]}
    issue = issues["unresolved_employee_identity"]
    assert issue["submitted_value"] == "Conseiller inconnu"
    assert issue["expected_format"] == ("Nom exact d\u2019un CA/CAA actif rattaché à cette agence.")
    row_values = {cell["field_name"]: cell["value"] for cell in issue["row_values"]}
    assert row_values["agency"] == "ARIANA"
    assert row_values["amount"] == "15000"
    assert row_values["reference"] == "must-not-be-returned"
    assert issues["missing_match_key"]["submitted_value"] == "must-not-be-returned"
    assert issues["missing_required_value"]["submitted_value"] == ""
    assert issues["missing_required_value"]["expected_format"] == (
        "Type de crédit présent dans les référentiels."
    )
