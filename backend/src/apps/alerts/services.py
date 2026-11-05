from uuid import UUID

from django.db import transaction

from apps.alerts.models import DelayAlert
from apps.imports.models import TB2SnapshotStagingRow, ValidationStatus
from apps.warehouse.models import FactCreditRequest


@transaction.atomic
def evaluate_delay_alerts(*, batch_id: UUID) -> list[str]:
    """Evaluate only the trusted monthly TB2 snapshot just published."""
    scopes = (
        TB2SnapshotStagingRow.objects.filter(
            batch_id=batch_id, validation_status=ValidationStatus.VALID, is_current=True
        )
        .values_list("agency_id", "reporting_period")
        .distinct()
    )
    created_ids: list[str] = []
    for agency_id, period in scopes:
        if period is None:
            continue
        month_start = period.replace(day=1)
        observed = FactCreditRequest.objects.filter(
            agency_id=agency_id, current_tb2_row__batch_id=batch_id
        ).select_related(
            "status", "ca_caa", "gp", "reception_date", "gp_assignment_date", "visit_date"
        )
        observed_ids: set[UUID] = set()
        active_rules: set[tuple[UUID, str]] = set()
        for fact in observed:
            observed_ids.add(fact.pk)
            if fact.status and fact.status.is_terminal:
                continue
            rule = None
            started = None
            role = ""
            name = ""
            if (
                fact.reception_date
                and not fact.gp_assignment_date
                and fact.reception_date.calendar_date < month_start
            ):
                rule, started, role, name = (
                    DelayAlert.Rule.RECEPTION_BLOCKED,
                    fact.reception_date.calendar_date,
                    "CA/CAA",
                    str(fact.ca_caa.name) if fact.ca_caa else "",
                )
            elif (
                fact.gp_assignment_date
                and not fact.visit_date
                and fact.gp_assignment_date.calendar_date < month_start
            ):
                rule, started, role, name = (
                    DelayAlert.Rule.VISIT_BLOCKED,
                    fact.gp_assignment_date.calendar_date,
                    "GP",
                    str(fact.gp.name) if fact.gp else "",
                )
            if rule is None or started is None:
                continue
            alert, created = DelayAlert.objects.get_or_create(
                credit_request=fact,
                rule=rule,
                defaults={
                    "agency_id": agency_id,
                    "reporting_period": period,
                    "started_on": started,
                    "responsible_role": role,
                    "responsible_name": name,
                },
            )
            if created:
                created_ids.append(str(alert.pk))
            if not created:
                previous_period = alert.reporting_period
                alert.reporting_period = period
                alert.started_on = started
                alert.responsible_role = role
                alert.responsible_name = name
                # A corrected re-upload of the same month is not an escalation.  Escalation
                # requires a later validated monthly observation confirming the same blockage.
                if period > previous_period and alert.state != DelayAlert.State.ESCALATED:
                    alert.state = DelayAlert.State.ESCALATED
                alert.save(
                    update_fields=[
                        "reporting_period",
                        "started_on",
                        "responsible_role",
                        "responsible_name",
                        "state",
                        "updated_at",
                    ]
                )
            active_rules.add((fact.pk, rule))
        # An absent dossier must not be treated as resolved: only a dossier observed in this
        # trusted snapshot can resolve its prior alert.
        stale_alerts = DelayAlert.objects.filter(
            agency_id=agency_id,
            credit_request_id__in=observed_ids,
            state__in=[
                DelayAlert.State.NEW,
                DelayAlert.State.ESCALATED,
            ],
        )
        stale_ids = [
            alert.pk
            for alert in stale_alerts
            if (alert.credit_request_id, alert.rule) not in active_rules
        ]
        if stale_ids:
            DelayAlert.objects.filter(pk__in=stale_ids).delete()
    return created_ids
