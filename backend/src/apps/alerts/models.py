from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class DelayAlert(UUIDModel, TimeStampedModel):
    class Rule(models.TextChoices):
        RECEPTION_BLOCKED = "reception_blocked", "Réception bloquée"
        VISIT_BLOCKED = "visit_blocked", "Visite bloquée"

    class State(models.TextChoices):
        NEW = "new", "Nouveau"
        ESCALATED = "escalated", "Escaladé"

    credit_request = models.ForeignKey(
        "warehouse.FactCreditRequest", on_delete=models.PROTECT, related_name="delay_alerts"
    )
    agency = models.ForeignKey(
        "warehouse.AgencyDimension", on_delete=models.PROTECT, related_name="delay_alerts"
    )
    rule = models.CharField(max_length=32, choices=Rule.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.NEW)
    reporting_period = models.DateField()
    started_on = models.DateField()
    responsible_role = models.CharField(max_length=8)
    responsible_name = models.CharField(max_length=160, blank=True)

    class Meta:
        db_table = '"alerts"."delay_alert"'
        ordering = ["state", "-reporting_period", "agency__name", "started_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["credit_request", "rule"], name="delay_alert_request_rule_uniq"
            )
        ]
        indexes = [
            models.Index(fields=["agency", "state"]),
            models.Index(fields=["reporting_period", "state"]),
        ]
