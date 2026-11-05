import pytest
from django.core.exceptions import ValidationError

from apps.data_quality.models import DataQualityIssue
from apps.imports.models import ImportBatch, TB1RequestStagingRow


def _create_batch(*, checksum_character: str = "a") -> ImportBatch:
    return ImportBatch.objects.create(
        original_filename="synthetic.xlsx",
        source_file="imports/synthetic.xlsx",
        workbook_type=ImportBatch.WorkbookType.TB1,
        checksum_sha256=checksum_character * 64,
        file_size=512,
    )


@pytest.mark.django_db
def test_quality_issue_rejects_a_row_from_another_batch() -> None:
    first_batch = _create_batch(checksum_character="c")
    second_batch = _create_batch(checksum_character="d")
    row = TB1RequestStagingRow.objects.create(
        batch=first_batch,
        sheet_name="Sheet1",
        source_row=2,
        row_hash="e" * 64,
    )
    issue = DataQualityIssue(
        batch=second_batch,
        tb1_row=row,
        severity=DataQualityIssue.Severity.ERROR,
        code="missing_reference",
        field_name="reference",
        message="Required reference is absent.",
    )

    with pytest.raises(ValidationError, match="staged row must belong"):
        issue.full_clean()
