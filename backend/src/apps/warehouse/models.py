from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel
from apps.warehouse.fields import EncryptedTextField

CODE_VALIDATOR = RegexValidator(
    regex=r"^[a-z][a-z0-9_]*$",
    message="Use lowercase letters, numbers, and underscores, starting with a letter.",
)


class DateDimension(models.Model):
    date_key = models.PositiveIntegerField(primary_key=True, editable=False)
    calendar_date = models.DateField(unique=True)
    day_of_week = models.PositiveSmallIntegerField(editable=False)
    day_of_month = models.PositiveSmallIntegerField(editable=False)
    week_of_year = models.PositiveSmallIntegerField(editable=False)
    month = models.PositiveSmallIntegerField(editable=False)
    month_name = models.CharField(max_length=16, editable=False)
    quarter = models.PositiveSmallIntegerField(editable=False)
    year = models.PositiveSmallIntegerField(editable=False)
    month_start = models.DateField(editable=False)
    quarter_start = models.DateField(editable=False)
    is_weekend = models.BooleanField(editable=False)

    class Meta:
        db_table = '"warehouse"."dim_date"'
        ordering = ["calendar_date"]
        indexes = [models.Index(fields=["year", "month"])]
        constraints = [
            models.CheckConstraint(condition=Q(month__gte=1, month__lte=12), name="dim_date_month"),
            models.CheckConstraint(
                condition=Q(quarter__gte=1, quarter__lte=4), name="dim_date_quarter"
            ),
        ]

    def __str__(self) -> str:
        return self.calendar_date.isoformat()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.sync_calendar_fields()
        _extend_update_fields(
            kwargs,
            "date_key",
            "day_of_week",
            "day_of_month",
            "week_of_year",
            "month",
            "month_name",
            "quarter",
            "year",
            "month_start",
            "quarter_start",
            "is_weekend",
        )
        super().save(*args, **kwargs)

    def sync_calendar_fields(self) -> None:
        value = self.calendar_date
        self.date_key = value.year * 10_000 + value.month * 100 + value.day
        self.day_of_week = value.isoweekday()
        self.day_of_month = value.day
        self.week_of_year = value.isocalendar().week
        self.month = value.month
        self.month_name = value.strftime("%B")
        self.quarter = (value.month - 1) // 3 + 1
        self.year = value.year
        self.month_start = value.replace(day=1)
        quarter_month = (self.quarter - 1) * 3 + 1
        self.quarter_start = value.replace(month=quarter_month, day=1)
        self.is_weekend = self.day_of_week >= 6


class AgencyDimension(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        unique=True,
        validators=[RegexValidator(r"^\d{4}$", "Use exactly four digits.")],
        help_text="Four-digit governed code embedded in request references.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = '"warehouse"."dim_agency"'
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="dim_agency_name_uniq"),
        ]

    def __str__(self) -> str:
        return self.name


class StaffDimension(UUIDModel, TimeStampedModel):
    """Shared implementation for operational CA and GP analytical dimensions."""

    name = EncryptedTextField()
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    agency = models.ForeignKey(
        AgencyDimension,
        on_delete=models.PROTECT,
        related_name="%(class)s_versions",
    )

    class Meta:
        abstract = True
        ordering = ["name"]
        indexes = [models.Index(fields=["agency", "is_active"])]

    def __str__(self) -> str:
        return f"Restricted {self.dimension_label} {self.pk}"

    @property
    def dimension_label(self) -> str:
        raise NotImplementedError


class CADimension(StaffDimension):
    class Meta(StaffDimension.Meta):
        db_table = '"warehouse"."dim_ca"'

    dimension_label = "CA / CAA"


class GPDimension(StaffDimension):
    class Meta(StaffDimension.Meta):
        db_table = '"warehouse"."dim_gp"'

    dimension_label = "GP"


class SelectableDimension(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=160, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CreditTypeDimension(SelectableDimension):
    class Meta(SelectableDimension.Meta):
        db_table = '"warehouse"."dim_credit_type"'


class ActivityDimension(SelectableDimension):
    class Meta(SelectableDimension.Meta):
        db_table = '"warehouse"."dim_activity"'


class RequestTypeDimension(SelectableDimension):
    class Meta(SelectableDimension.Meta):
        db_table = '"warehouse"."dim_request_type"'


class StatusDimension(UUIDModel, TimeStampedModel):
    code = models.CharField(max_length=48, unique=True, validators=[CODE_VALIDATOR])
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class PipelineStage(models.TextChoices):
        INTAKE = "intake", "Intake"
        WAITING_VISIT = "waiting_visit", "Waiting for visit"
        WAITING_DECISION = "waiting_decision", "Waiting for decision"
        WAITING_DISBURSEMENT = "waiting_disbursement", "Waiting for disbursement"
        COMPLETED = "completed", "Completed"

    pipeline_stage = models.CharField(max_length=32, choices=PipelineStage.choices)
    is_terminal = models.BooleanField(default=False)
    is_funded = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)

    class Meta:
        db_table = '"warehouse"."dim_status"'
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(is_funded=True, is_rejected=True),
                name="dim_status_single_outcome",
            ),
            models.CheckConstraint(
                condition=(Q(is_funded=False, is_rejected=False) | Q(is_terminal=True)),
                name="dim_status_outcome_terminal",
            ),
        ]
        indexes = [models.Index(fields=["pipeline_stage", "is_active"])]


class RejectionReasonDimension(SelectableDimension):
    class Meta(SelectableDimension.Meta):
        db_table = '"warehouse"."dim_rejection_reason"'


class FactCreditRequest(UUIDModel, TimeStampedModel):
    agency = models.ForeignKey(AgencyDimension, on_delete=models.PROTECT, related_name="requests")
    gp = models.ForeignKey(
        GPDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gp_requests",
    )
    ca_caa = models.ForeignKey(
        CADimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ca_caa_requests",
    )
    credit_type = models.ForeignKey(
        CreditTypeDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requests",
    )
    activity = models.ForeignKey(
        ActivityDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="requests"
    )
    request_type = models.ForeignKey(
        RequestTypeDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requests",
    )
    status = models.ForeignKey(
        StatusDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="requests"
    )
    rejection_reason = models.ForeignKey(
        RejectionReasonDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requests",
    )

    reference = models.CharField(
        max_length=32,
        blank=True,
        db_index=True,
        help_text="Canonical governed request reference for operational display and lookup.",
    )
    missing_from_latest_tb2_period = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Reporting month of the latest complete TB2 submission in which this dossier "
            "was absent; it does not change the business status."
        ),
    )
    amount = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)

    request_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reception_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    gp_assignment_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    visit_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    disbursement_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    rejection_date = models.ForeignKey(
        DateDimension, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    current_tb1_row = models.ForeignKey(
        "imports.TB1RequestStagingRow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="controlling_facts",
    )
    current_tb2_row = models.ForeignKey(
        "imports.TB2SnapshotStagingRow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="controlling_facts",
    )

    class Meta:
        db_table = '"warehouse"."fact_credit_request"'
        ordering = ["-request_date_id", "agency_id", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "reference"],
                name="fact_request_agency_reference_uniq",
            ),
            models.CheckConstraint(
                condition=Q(amount__isnull=True) | Q(amount__gte=0),
                name="fact_request_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(disbursement_date__isnull=True) | Q(rejection_date__isnull=True),
                name="fact_request_single_outcome_date",
            ),
        ]
        indexes = [
            models.Index(fields=["request_date", "agency"]),
            models.Index(fields=["status", "request_date"]),
            models.Index(fields=["gp", "request_date"]),
            models.Index(fields=["ca_caa", "request_date"]),
        ]

    def clean(self) -> None:
        super().clean()
        gp = self.gp
        ca_caa = self.ca_caa
        if self.gp_id and gp is not None and gp.agency_id != self.agency_id:
            raise ValidationError({"gp": "GP assignment must belong to the request agency."})
        if self.ca_caa_id and ca_caa is not None and ca_caa.agency_id != self.agency_id:
            raise ValidationError(
                {"ca_caa": "CA/CAA assignment must belong to the request agency."}
            )

    def __str__(self) -> str:
        return f"Credit request {self.pk}"


class CreditRequestStatusHistory(UUIDModel, TimeStampedModel):
    """Immutable lifecycle transition derived from a committed TB1 or TB2 row."""

    credit_request = models.ForeignKey(
        FactCreditRequest,
        on_delete=models.PROTECT,
        related_name="status_history",
    )
    status = models.ForeignKey(StatusDimension, on_delete=models.PROTECT, related_name="+")
    effective_date = models.ForeignKey(DateDimension, on_delete=models.PROTECT, related_name="+")
    source_tb1_row = models.ForeignKey(
        "imports.TB1RequestStagingRow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="status_history_entries",
    )
    source_tb2_row = models.ForeignKey(
        "imports.TB2SnapshotStagingRow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="status_history_entries",
    )

    class Meta:
        db_table = '"warehouse"."credit_request_status_history"'
        ordering = ["credit_request_id", "effective_date_id", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(source_tb1_row__isnull=False, source_tb2_row__isnull=True)
                    | Q(source_tb1_row__isnull=True, source_tb2_row__isnull=False)
                ),
                name="status_history_exactly_one_source",
            )
        ]
        indexes = [
            models.Index(fields=["credit_request", "effective_date"]),
            models.Index(fields=["status", "effective_date"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Credit-request status history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *_args: Any, **_kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Credit-request status history cannot be deleted.")

    def __str__(self) -> str:
        return f"{self.credit_request_id}: {self.status.code}"


def _extend_update_fields(kwargs: dict[str, Any], *derived_fields: str) -> None:
    update_fields = kwargs.get("update_fields")
    if update_fields:
        kwargs["update_fields"] = set(update_fields) | set(derived_fields)
