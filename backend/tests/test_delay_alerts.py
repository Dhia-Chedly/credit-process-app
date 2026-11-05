from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.alerts.models import DelayAlert
from apps.alerts.services import evaluate_delay_alerts
from apps.imports.models import ImportBatch, MatchStatus, TB2SnapshotStagingRow, ValidationStatus
from apps.warehouse.models import AgencyDimension, DateDimension, FactCreditRequest, StatusDimension


@pytest.mark.django_db
def test_active_operator_can_resolve_and_delete_an_alert() -> None:
    user = User.objects.create_user(username="operator", password="secure-test-password")
    agency = AgencyDimension.objects.create(name="Agence de test", code="9990")
    request = FactCreditRequest.objects.create(agency=agency, reference="9990/001/P/01082026")
    alert = DelayAlert.objects.create(
        credit_request=request,
        agency=agency,
        rule=DelayAlert.Rule.VISIT_BLOCKED,
        reporting_period=date(2026, 8, 1),
        started_on=date(2026, 7, 28),
        responsible_role="GP",
        responsible_name="GP de test",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.delete(f"/api/delay-alerts/{alert.pk}/resolve/")

    assert response.status_code == 204
    assert not DelayAlert.objects.filter(pk=alert.pk).exists()


@pytest.mark.django_db
def test_stage_change_resolves_the_previous_rule_and_keeps_current_blockage() -> None:
    agency = AgencyDimension.objects.create(name="Agence de test", code="9990")
    period = date(2026, 8, 1)
    batch = ImportBatch.objects.create(
        original_filename="tb2.xlsx",
        source_file="imports/test/tb2.xlsx",
        workbook_type=ImportBatch.WorkbookType.TB2,
        status=ImportBatch.Status.COMPLETED,
        checksum_sha256="a" * 64,
        file_size=1,
        detected_agency=agency,
        reporting_period=period,
    )
    row = TB2SnapshotStagingRow.objects.create(
        batch=batch,
        agency=agency,
        sheet_name="Feuille 1",
        source_row=1,
        reporting_period=period,
        row_hash="b" * 64,
        reference="9990/002/P/01082026",
        validation_status=ValidationStatus.VALID,
        match_status=MatchStatus.MATCHED,
    )
    reception_date = DateDimension.objects.create(calendar_date=date(2026, 7, 15))
    assignment_date = DateDimension.objects.create(calendar_date=date(2026, 7, 20))
    status = StatusDimension.objects.create(
        code="awaiting_visit",
        name="En attente de visite",
        pipeline_stage=StatusDimension.PipelineStage.WAITING_VISIT,
    )
    request = FactCreditRequest.objects.create(
        agency=agency,
        reference=row.reference,
        status=status,
        reception_date=reception_date,
        gp_assignment_date=assignment_date,
        current_tb2_row=row,
    )
    reception_alert = DelayAlert.objects.create(
        credit_request=request,
        agency=agency,
        rule=DelayAlert.Rule.RECEPTION_BLOCKED,
        reporting_period=date(2026, 7, 1),
        started_on=reception_date.calendar_date,
        responsible_role="CA/CAA",
    )

    evaluate_delay_alerts(batch_id=batch.pk)

    visit_alert = DelayAlert.objects.get(
        credit_request=request,
        rule=DelayAlert.Rule.VISIT_BLOCKED,
    )
    assert not DelayAlert.objects.filter(pk=reception_alert.pk).exists()
    assert visit_alert.state == DelayAlert.State.NEW


@pytest.mark.django_db
def test_alert_list_returns_page_counts_and_server_side_filters() -> None:
    user = User.objects.create_user(username="reader", password="secure-test-password")
    agency = AgencyDimension.objects.create(name="Agence de test", code="9990")
    for index in range(51):
        request = FactCreditRequest.objects.create(
            agency=agency,
            reference=f"9990/{index:05d}/P/01082026",
        )
        DelayAlert.objects.create(
            credit_request=request,
            agency=agency,
            rule=DelayAlert.Rule.VISIT_BLOCKED,
            state=DelayAlert.State.ESCALATED if index == 50 else DelayAlert.State.NEW,
            reporting_period=date(2026, 8, 1),
            started_on=date(2026, 7, 28),
            responsible_role="GP",
            responsible_name="GP de test",
        )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/delay-alerts/?agency={agency.pk}&state=new")

    assert response.status_code == 200
    assert response.data["count"] == 50
    assert len(response.data["results"]) == 50
    assert response.data["summary"] == {"new": 50, "escalated": 1}
    assert response.data["filter_options"]["agencies"] == [
        {"agency_id": agency.pk, "agency__name": agency.name}
    ]

    second_page = client.get(
        f"/api/delay-alerts/?agency={agency.pk}&state=escalated&responsible=GP%20de%20test"
    )
    assert second_page.data["count"] == 1
    assert second_page.data["results"][0]["state"] == DelayAlert.State.ESCALATED
