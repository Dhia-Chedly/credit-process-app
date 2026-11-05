from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel
from apps.warehouse.models import AgencyDimension

SHA256_VALIDATOR = RegexValidator(
    regex=r"^[0-9a-f]{64}$",
    message="Enter a lowercase hexadecimal SHA-256 checksum.",
)


def import_file_path(instance: ImportBatch, filename: str) -> str:
    """Store uploads under opaque IDs so paths never expose source filenames."""
    suffix = Path(filename).suffix.casefold()
    safe_suffix = suffix if suffix in {".xlsx", ".xlsm"} else ".upload"
    uploaded_at = timezone.now()
    return f"imports/{uploaded_at:%Y/%m}/{instance.pk}{safe_suffix}"


class ImportBatch(UUIDModel, TimeStampedModel):
    class WorkbookType(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        TB1 = "tb1", "TB1 - credit requests"
        TB2 = "tb2", "TB2 - outstanding loans"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Completed with quarantined rows"
        FAILED = "failed", "Failed"

    original_filename = models.CharField(max_length=255)
    source_file = models.FileField(upload_to=import_file_path, max_length=500)
    workbook_type = models.CharField(
        max_length=16,
        choices=WorkbookType.choices,
        default=WorkbookType.UNKNOWN,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    checksum_sha256 = models.CharField(
        max_length=64,
        unique=True,
        validators=[SHA256_VALIDATOR],
    )
    file_size = models.PositiveBigIntegerField(help_text="Uploaded file size in bytes.")
    detected_agency = models.ForeignKey(
        AgencyDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_batches",
    )
    reporting_period = models.DateField(
        null=True,
        blank=True,
        help_text="First calendar day of the reporting month when it can be detected.",
    )
    sheet_name = models.CharField(max_length=255, blank=True)
    rows_discovered = models.PositiveIntegerField(default=0)
    rows_imported = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(
        blank=True,
        help_text="Sanitized failure summary; never include workbook cell values.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_batches",
    )

    class Meta:
        db_table = '"ingestion"."import_batch"'
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["workbook_type", "reporting_period"]),
            models.Index(fields=["detected_agency", "reporting_period"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(rows_discovered__gte=F("rows_imported") + F("rows_rejected")),
                name="imports_batch_row_counts_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Import {self.pk} ({self.get_status_display()})"


class ValidationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VALID = "valid", "Valid"
    INVALID = "invalid", "Invalid"


class MatchStatus(models.TextChoices):
    UNMATCHED = "unmatched", "Unmatched"
    MATCHED = "matched", "Matched"
    BLOCKED = "blocked", "Blocked"


# Compatibility values for the warehouse publication boundary.  These are not
# stored columns: the persistent staging state is the explicit validation and
# match status above.
class StagingRowStatus(models.TextChoices):
    STAGED = "staged", "Staged"
    QUARANTINED = "quarantined", "Quarantined"
    COMMITTED = "committed", "Committed"


class TypedStagingRow(UUIDModel):
    """Minimal, non-client staging fields shared by TB1 and TB2."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE)
    agency = models.ForeignKey(
        AgencyDimension,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    sheet_name = models.CharField(max_length=255, default="")
    source_row = models.PositiveIntegerField()
    reporting_period = models.DateField(
        null=True,
        blank=True,
        help_text="First day of the source row reporting month when it can be determined.",
    )
    is_current = models.BooleanField(
        default=True,
        help_text="False when a newer import replaces this agency, period, and workbook scope.",
    )
    row_hash = models.CharField(max_length=64, default="", validators=[SHA256_VALIDATOR])
    reference = models.CharField(
        max_length=32,
        blank=True,
        db_index=True,
        help_text="Canonical governed request reference, retained for operational lookup.",
    )
    correction_values = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Controlled non-client workbook values used only to display correction rows; "
            "ignored client/comment fields are prohibited."
        ),
    )
    validation_status = models.CharField(
        max_length=16,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    match_status = models.CharField(
        max_length=16,
        choices=MatchStatus.choices,
        default=MatchStatus.UNMATCHED,
    )

    class Meta:
        abstract = True

    @property
    def status(self) -> str:
        if (
            self.validation_status == ValidationStatus.INVALID
            or self.match_status == MatchStatus.BLOCKED
        ):
            return StagingRowStatus.QUARANTINED
        if (
            self.validation_status == ValidationStatus.VALID
            and self.match_status == MatchStatus.MATCHED
        ):
            return StagingRowStatus.COMMITTED
        return StagingRowStatus.STAGED

    @property
    def detected_agency(self) -> AgencyDimension | None:
        """Use the row agency for multi-agency workbooks, with batch fallback."""

        return self.agency or self.batch.detected_agency


class TB1RequestStagingRow(TypedStagingRow):
    """One typed, immutable TB1 request row."""

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="tb1_request_rows",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    credit_type_name = models.CharField(max_length=120, blank=True)
    request_type_name = models.CharField(max_length=120, blank=True)
    activity_name = models.CharField(max_length=120, blank=True)
    request_date = models.DateField(null=True, blank=True)
    matched_tb2 = models.ForeignKey(
        "TB2SnapshotStagingRow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_tb1_rows",
    )

    class Meta:
        db_table = '"ingestion"."stg_tb1_request_row"'
        ordering = ["batch_id", "sheet_name", "source_row"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "sheet_name", "source_row"],
                name="imports_tb1_stage_coordinate_uniq",
            ),
            models.CheckConstraint(
                condition=Q(source_row__gte=1),
                name="imports_tb1_stage_positive_row",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "validation_status", "match_status"]),
            models.Index(
                fields=["agency", "reporting_period", "is_current"],
                name="imports_tb1_scope_current_idx",
            ),
            models.Index(fields=["agency", "reference"]),
        ]

    def __str__(self) -> str:
        return f"TB1 {self.batch_id}, sheet {self.sheet_name}, row {self.source_row}"


class TB2SnapshotStagingRow(TypedStagingRow):
    """One typed, immutable TB2 lifecycle snapshot row."""

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="tb2_snapshot_rows",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    gp_name = models.CharField(max_length=160, blank=True)
    ca_name = models.CharField(max_length=160, blank=True)
    received_at_agency_date = models.DateField(null=True, blank=True)
    assigned_to_gp_date = models.DateField(null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True)
    disbursement_date = models.DateField(null=True, blank=True)
    rejection_date = models.DateField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=160, blank=True)
    matched_tb1 = models.ForeignKey(
        TB1RequestStagingRow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_tb2_rows",
    )

    class Meta:
        db_table = '"ingestion"."stg_tb2_snapshot_row"'
        ordering = ["batch_id", "sheet_name", "source_row"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "sheet_name", "source_row"],
                name="imports_tb2_stage_coordinate_uniq",
            ),
            models.CheckConstraint(
                condition=Q(source_row__gte=1),
                name="imports_tb2_stage_positive_row",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "validation_status", "match_status"]),
            models.Index(
                fields=["agency", "reporting_period", "is_current"],
                name="imports_tb2_scope_current_idx",
            ),
            models.Index(fields=["agency", "reference"]),
        ]

    def __str__(self) -> str:
        return f"TB2 {self.batch_id}, sheet {self.sheet_name}, row {self.source_row}"
