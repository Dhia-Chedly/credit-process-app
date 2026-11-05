from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.imports.models import (
    ImportBatch,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
)

ISSUE_CODE_VALIDATOR = RegexValidator(
    regex=r"^[a-z][a-z0-9_]*$",
    message="Use lowercase letters, numbers, and underscores, starting with a letter.",
)


class DataQualityIssue(UUIDModel, TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Information"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="quality_issues",
    )
    tb1_row = models.ForeignKey(
        TB1RequestStagingRow,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    tb2_row = models.ForeignKey(
        TB2SnapshotStagingRow,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    severity = models.CharField(max_length=16, choices=Severity.choices)
    code = models.CharField(max_length=64, validators=[ISSUE_CODE_VALIDATOR])
    field_name = models.CharField(max_length=64, blank=True)
    message = models.TextField(
        help_text="Sanitized explanation; source values remain on the protected staged row.",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Structural metadata and whitelisted non-client correction values only; do not copy "
            "client names, references, phone numbers, addresses, or comments."
        ),
    )

    class Meta:
        db_table = '"ingestion"."stg_data_quality_issue"'
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "tb1_row", "code", "field_name"],
                name="data_quality_tb1_row_issue_uniq",
            ),
            models.UniqueConstraint(
                fields=["batch", "tb2_row", "code", "field_name"],
                name="data_quality_tb2_row_issue_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "severity"]),
            models.Index(fields=["code"]),
        ]

    def clean(self) -> None:
        super().clean()
        rows = tuple(row for row in (self.tb1_row, self.tb2_row) if row is not None)
        if rows and self.batch_id and rows[0].batch_id != self.batch_id:
            raise ValidationError("The staged row must belong to the selected import batch.")

    def __str__(self) -> str:
        location = self.tb1_row_id or self.tb2_row_id or "workbook"
        return f"{self.code} on {location}"
