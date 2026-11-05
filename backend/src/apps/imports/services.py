from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.alerts.services import evaluate_delay_alerts
from apps.core.permissions import has_active_user
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import (
    ImportBatch,
    MatchStatus,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
    ValidationStatus,
)
from apps.imports.parser import (
    TEMPLATE_HEADERS,
    AgencySource,
    CellValueError,
    InvalidWorkbookError,
    IssueSeverity,
    ParsedRow,
    ParsedWorkbook,
    ParserConfigurationError,
    UnsupportedWorkbookError,
    ValidationIssue,
    WorkbookKind,
    WorkbookLimitError,
    WorkbookParserError,
    infer_reporting_period,
    parse_canonical_reference,
    parse_workbook,
)
from apps.warehouse.crypto import normalize_match_value
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditTypeDimension,
    FactCreditRequest,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    StatusDimension,
)
from apps.warehouse.services import (
    WarehouseLoadError,
    WarehouseLoadResult,
    ensure_status_dimensions,
    load_credit_request,
)

TERMINAL_IMPORT_STATUSES = {
    ImportBatch.Status.COMPLETED,
    ImportBatch.Status.PARTIAL,
}
logger = logging.getLogger(__name__)

VISIBLE_ISSUE_VALUE_FIELDS = frozenset(
    {
        "agency",
        "reference",
        "request_date",
        "request_type",
        "amount",
        "credit_type",
        "activity_category",
        "received_at_agency_date",
        "counsellor_name",
        "assigned_to_gp_date",
        "gp_name",
        "visit_date",
        "status",
        "outcome_date",
        "rejection_reason",
    }
)


class AgencyScopeViolationError(WorkbookParserError):
    """A bound agency manager attempted to publish another agency's workbook."""


class ReplayRequiresReconciliationError(WorkbookParserError):
    """A manually forced replay would remove previously published lineage."""


def process_batch(batch_id: str) -> dict[str, int | str]:
    """Parse and transactionally publish one idempotent import batch."""

    try:
        batch = ImportBatch.objects.get(pk=batch_id)
    except (ImportBatch.DoesNotExist, ValueError):
        return {"batch_id": batch_id, "status": "missing"}

    with transaction.atomic():
        batch = ImportBatch.objects.select_for_update().get(pk=batch.pk)
        # Populate the nullable relation in a separate query: PostgreSQL cannot
        # lock the nullable side of the outer join that ``select_related`` uses.
        _ = batch.uploaded_by
        if batch.status in TERMINAL_IMPORT_STATUSES:
            return _batch_summary(batch)
        batch.status = ImportBatch.Status.PROCESSING
        batch.started_at = batch.started_at or timezone.now()
        batch.finished_at = None
        batch.error_message = ""
        batch.save(
            update_fields=[
                "status",
                "started_at",
                "finished_at",
                "error_message",
                "updated_at",
            ]
        )

    try:
        parsed = _parse_batch_workbook(batch)
        if not parsed.profile.schema_valid:
            raise WorkbookParserError("The normalized batch did not satisfy its schema.")
        _validate_uploader_agency_scope(batch, parsed)
        return _publish_batch(batch.pk, parsed)
    except WorkbookParserError as exc:
        return _mark_failed(batch.pk, _failure_code(exc), _sanitized_failure_message(exc))
    except Exception:
        logger.error("Import batch %s failed during processing.", batch.pk)
        return _mark_failed(
            batch.pk,
            "internal_processing_error",
            "The workbook could not be processed because of an internal error.",
        )
    finally:
        _discard_source_workbook(batch.pk)


def _discard_source_workbook(batch_id: Any) -> None:
    """Delete the temporary workbook once parsing has completed.

    Staging keeps only governed operational fields; source workbooks may contain
    client data and are therefore never retained.
    """

    with transaction.atomic():
        batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
        source_name = batch.source_file.name
        if not source_name:
            return
        batch.source_file.name = ""
        batch.save(update_fields=["source_file", "updated_at"])
    default_storage.delete(source_name)


def _parse_batch_workbook(batch: ImportBatch) -> ParsedWorkbook:
    """Parse a workbook using only the governed built-in TB1/TB2 headers."""

    return parse_workbook(
        batch.source_file.path,
        source_name=batch.original_filename,
    )


def _validate_uploader_agency_scope(batch: ImportBatch, parsed: ParsedWorkbook) -> None:
    """Reauthorize the administrative uploader before publishing parsed data."""

    uploader = batch.uploaded_by
    if uploader is None:
        # Retained and command-created batches may predate governed uploader identity.
        return
    if has_active_user(uploader):
        return
    _ = parsed
    raise AgencyScopeViolationError("Only an active user may publish imported workbooks.")


def _publish_batch(batch_id: Any, parsed: ParsedWorkbook) -> dict[str, int | str]:
    """Stage a workbook, then publish only valid exact TB1/TB2 pairs."""

    with transaction.atomic():
        batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
        if batch.status in TERMINAL_IMPORT_STATUSES:
            return _batch_summary(batch)
        if (
            TB1RequestStagingRow.objects.filter(batch=batch).exists()
            or TB2SnapshotStagingRow.objects.filter(batch=batch).exists()
        ):
            raise ReplayRequiresReconciliationError(
                "This batch already has published import evidence and requires governed "
                "warehouse reconciliation before replay."
            )

        DataQualityIssue.objects.filter(batch=batch).delete()
        ensure_status_dimensions()
        agency_cache: dict[tuple[str, str], AgencyDimension] = {}
        detected_agency = _resolve_agency(
            parsed.metadata.agency,
            agency_cache,
            source=AgencySource.FILENAME,
        )
        batch.workbook_type = parsed.metadata.kind.value
        batch.detected_agency = detected_agency
        batch.reporting_period = parsed.metadata.reporting_period
        batch.sheet_name = parsed.sheets[0].metadata.name if len(parsed.sheets) == 1 else ""
        batch.save(
            update_fields=[
                "workbook_type",
                "detected_agency",
                "reporting_period",
                "sheet_name",
                "updated_at",
            ]
        )
        _discard_prior_rejected_reports(batch)
        row_validation: list[
            tuple[ParsedRow, AgencyDimension | None, tuple[ValidationIssue, ...]]
        ] = []
        duplicate_keys: set[tuple[object, str]] = set()

        for workbook_issue in parsed.issues:
            _create_quality_issue(batch=batch, row=None, issue=workbook_issue)
        for sheet in parsed.sheets:
            for sheet_issue in sheet.issues:
                _create_quality_issue(batch=batch, row=None, issue=sheet_issue)

        for parsed_row in parsed.rows:
            row_agency = (
                _resolve_agency(
                    parsed_row.agency,
                    agency_cache,
                    source=parsed_row.agency_source,
                )
                or detected_agency
            )
            issues = list(parsed_row.issues)
            if parsed.metadata.kind is WorkbookKind.TB1:
                if parsed_row.agency_source is not AgencySource.FILENAME:
                    issues.append(
                        _template_rule_issue(
                            code="tb1_requires_filename_agency",
                            message="TB1 agency must be supplied by the workbook filename.",
                            parsed_row=parsed_row,
                            field="agency",
                        )
                    )
                if infer_reporting_period(parsed_row.sheet_name) is None:
                    issues.append(
                        _template_rule_issue(
                            code="tb1_requires_sheet_period",
                            message=(
                                "TB1 reporting period must be supplied by a month/year "
                                "worksheet name."
                            ),
                            parsed_row=parsed_row,
                            field="reporting_period",
                        )
                    )
            elif parsed.metadata.kind is WorkbookKind.TB2 and (
                parsed_row.agency_source is not AgencySource.SHEET
            ):
                issues.append(
                    _template_rule_issue(
                        code="tb2_requires_sheet_agency",
                        message="TB2 agency must be supplied by the worksheet name.",
                        parsed_row=parsed_row,
                        field="agency",
                    )
                )
            if row_agency is None:
                issues.append(
                    ValidationIssue(
                        code="missing_agency",
                        message="The source agency could not be determined.",
                        severity=IssueSeverity.ERROR,
                        field="agency",
                        sheet_name=parsed_row.sheet_name,
                        row_number=parsed_row.source_row,
                    )
                )
            elif parsed.metadata.kind is WorkbookKind.TB2:
                issues.extend(
                    _employee_identity_issues(
                        agency=row_agency,
                        data=parsed_row.data,
                        parsed_row=parsed_row,
                    )
                )
            if row_agency is not None:
                issues.extend(
                    _governed_reference_issues(
                        agency=row_agency,
                        data=parsed_row.data,
                        parsed_row=parsed_row,
                    )
                )
            issues.extend(
                _governed_dimension_issues(
                    data=parsed_row.data,
                    source_kind=parsed.metadata.kind,
                    parsed_row=parsed_row,
                )
            )
            reference = _stage_text(parsed_row.data.get("reference"))
            if not reference:
                issues.append(
                    ValidationIssue(
                        code="missing_required_value",
                        message="La référence est obligatoire pour rapprocher les fichiers.",
                        severity=IssueSeverity.ERROR,
                        field="reference",
                        sheet_name=parsed_row.sheet_name,
                        row_number=parsed_row.source_row,
                    )
                )
            elif row_agency is not None and (row_agency.pk, reference) in duplicate_keys:
                issues.append(
                    ValidationIssue(
                        code="duplicate_reference_in_agency",
                        message=(
                            "Cette référence apparaît plusieurs fois pour la même agence "
                            "dans cet import."
                        ),
                        severity=IssueSeverity.ERROR,
                        field="reference",
                        sheet_name=parsed_row.sheet_name,
                        row_number=parsed_row.source_row,
                    )
                )
            elif row_agency is not None:
                duplicate_keys.add((row_agency.pk, reference))
            row_validation.append((parsed_row, row_agency, _deduplicate_issues(issues)))

        blocking_row_count = sum(
            any(issue.severity is IssueSeverity.ERROR for issue in issues)
            for _parsed_row, _agency, issues in row_validation
        )
        workbook_issues = [
            *parsed.issues,
            *(issue for sheet in parsed.sheets for issue in sheet.issues),
        ]
        blocking_workbook_issue = any(
            issue.severity is IssueSeverity.ERROR for issue in workbook_issues
        )
        if blocking_row_count or blocking_workbook_issue:
            for parsed_row, _row_agency, row_issues in row_validation:
                for issue in row_issues:
                    _create_quality_issue(
                        batch=batch,
                        row=None,
                        issue=issue,
                        parsed_row=parsed_row,
                        source_kind=parsed.metadata.kind,
                    )
            batch.status = ImportBatch.Status.FAILED
            batch.rows_discovered = parsed.profile.row_count
            batch.rows_imported = 0
            batch.rows_rejected = blocking_row_count
            batch.finished_at = timezone.now()
            batch.error_message = (
                "Le fichier contient des erreurs à corriger. Aucune ligne n\u2019a été importée."
            )
            batch.save(
                update_fields=[
                    "status",
                    "rows_discovered",
                    "rows_imported",
                    "rows_rejected",
                    "finished_at",
                    "error_message",
                    "updated_at",
                ]
            )
            return _batch_summary(batch)

        for parsed_row, row_agency, row_issues in row_validation:
            stage = _create_typed_stage(
                batch=batch,
                parsed_row=parsed_row,
                source_kind=parsed.metadata.kind,
                agency=row_agency,
            )
            for issue in row_issues:
                _create_quality_issue(
                    batch=batch,
                    row=stage,
                    issue=issue,
                    parsed_row=parsed_row,
                )
            stage.validation_status = ValidationStatus.VALID
            stage.save(update_fields=["validation_status"])

        _supersede_prior_scopes(batch=batch)
        imported_count, blocked_count = _match_and_publish()
        _mark_absent_from_latest_tb2(batch=batch)
        rejected_count = blocked_count
        batch.status = (
            ImportBatch.Status.PARTIAL if rejected_count else ImportBatch.Status.COMPLETED
        )
        batch.rows_discovered = parsed.profile.row_count
        batch.rows_imported = imported_count
        batch.rows_rejected = rejected_count
        batch.finished_at = timezone.now()
        batch.error_message = ""
        batch.save(
            update_fields=[
                "workbook_type",
                "status",
                "detected_agency",
                "reporting_period",
                "rows_discovered",
                "rows_imported",
                "rows_rejected",
                "finished_at",
                "error_message",
                "updated_at",
            ]
        )
        if (
            batch.workbook_type == WorkbookKind.TB2.value
            and batch.status == ImportBatch.Status.COMPLETED
        ):
            alert_ids = evaluate_delay_alerts(batch_id=batch.pk)
            if alert_ids:
                from apps.alerts.tasks import send_delay_alert_emails

                transaction.on_commit(lambda: send_delay_alert_emails.delay(alert_ids))
        return _batch_summary(batch)


def _discard_prior_rejected_reports(batch: ImportBatch) -> None:
    """Retain only the newest rejected correction report for a logical follow-up."""

    prior = ImportBatch.objects.filter(status=ImportBatch.Status.FAILED).exclude(pk=batch.pk)
    if batch.workbook_type == WorkbookKind.TB1.value and batch.detected_agency_id:
        prior = prior.filter(
            workbook_type=WorkbookKind.TB1.value,
            detected_agency_id=batch.detected_agency_id,
        )
    elif batch.workbook_type == WorkbookKind.TB2.value and batch.reporting_period:
        prior = prior.filter(
            workbook_type=WorkbookKind.TB2.value,
            reporting_period=batch.reporting_period,
        )
    else:
        return
    for previous in prior:
        source_name = previous.source_file.name
        previous.delete()
        if source_name:
            default_storage.delete(source_name)


def _create_typed_stage(
    *,
    batch: ImportBatch,
    parsed_row: ParsedRow,
    source_kind: WorkbookKind,
    agency: AgencyDimension | None,
) -> TB1RequestStagingRow | TB2SnapshotStagingRow:
    data = parsed_row.data
    common: dict[str, object] = {
        "batch": batch,
        "agency": agency,
        "sheet_name": parsed_row.sheet_name,
        "source_row": parsed_row.source_row,
        "reporting_period": parsed_row.reporting_period,
        "is_current": True,
        "row_hash": _row_fingerprint(parsed_row),
        "reference": _stage_text(data.get("reference"))[:32],
        "correction_values": _correction_values(parsed_row, source_kind),
        "validation_status": ValidationStatus.PENDING,
        "match_status": MatchStatus.UNMATCHED,
    }
    request_values: dict[str, object] = {
        "amount": _stage_decimal(data.get("amount")),
        "credit_type_name": _stage_text(data.get("credit_type"))[:120],
        "request_type_name": _stage_text(data.get("request_type"))[:120],
        "activity_name": _stage_text(data.get("activity_category"))[:120],
        "request_date": _stage_date(data.get("request_date")),
    }
    if source_kind is WorkbookKind.TB1:
        return TB1RequestStagingRow.objects.create(**common, **request_values)
    return TB2SnapshotStagingRow.objects.create(
        **common,
        amount=_stage_decimal(data.get("amount")),
        received_at_agency_date=_stage_date(data.get("received_at_agency_date")),
        assigned_to_gp_date=_stage_date(data.get("assigned_to_gp_date")),
        gp_name=_stage_text(data.get("gp_name"))[:160],
        ca_name=_stage_text(data.get("counsellor_name"))[:160],
        visit_date=_stage_date(data.get("visit_date")),
        disbursement_date=_stage_date(data.get("disbursement_date")),
        rejection_date=_stage_date(data.get("rejection_date")),
        rejection_reason=_stage_text(data.get("rejection_reason"))[:160],
    )


def _match_and_publish() -> tuple[int, int]:
    """Match source rows and refresh facts when a later TB2 snapshot arrives."""

    published = 0
    blocked = 0
    active_batch_statuses = [
        ImportBatch.Status.PROCESSING,
        ImportBatch.Status.COMPLETED,
        ImportBatch.Status.PARTIAL,
    ]
    tb1_rows = TB1RequestStagingRow.objects.filter(
        batch__status__in=active_batch_statuses,
        agency__isnull=False,
        is_current=True,
        validation_status=ValidationStatus.VALID,
        match_status=MatchStatus.UNMATCHED,
    ).select_related("batch")
    for tb1 in tb1_rows:
        candidates = list(
            TB2SnapshotStagingRow.objects.filter(
                batch__status__in=active_batch_statuses,
                agency_id=tb1.agency_id,
                is_current=True,
                validation_status=ValidationStatus.VALID,
                match_status=MatchStatus.UNMATCHED,
                reference=tb1.reference,
            ).select_related("batch")[:2]
        )
        if not candidates:
            continue
        if len(candidates) > 1:
            _block_pair(
                tb1=tb1,
                tb2_rows=candidates,
                code="ambiguous_match",
                message="More than one TB2 row has this match key.",
            )
            blocked += 1 + len(candidates)
            continue
        if _publish_pair(tb1=tb1, tb2=candidates[0]):
            published += 1
        else:
            blocked += 2

    # A TB1 request is an initial fact and therefore normally arrives once. TB2 is a periodic
    # snapshot: a new monthly row must be allowed to reuse that already-matched TB1 row and move
    # ``current_tb2_row`` forward without deleting the older TB2 staging evidence.
    tb2_rows = TB2SnapshotStagingRow.objects.filter(
        batch__status__in=active_batch_statuses,
        agency__isnull=False,
        is_current=True,
        validation_status=ValidationStatus.VALID,
        match_status=MatchStatus.UNMATCHED,
    ).select_related("batch")
    for tb2 in tb2_rows:
        tb1_candidates = list(
            TB1RequestStagingRow.objects.filter(
                batch__status__in=active_batch_statuses,
                agency_id=tb2.agency_id,
                is_current=True,
                validation_status=ValidationStatus.VALID,
                match_status__in=[MatchStatus.UNMATCHED, MatchStatus.MATCHED],
                reference=tb2.reference,
            ).select_related("batch")[:2]
        )
        if not tb1_candidates:
            continue
        if len(tb1_candidates) > 1:
            _block_pair(
                tb1=tb1_candidates[0],
                tb2_rows=[tb2],
                code="ambiguous_match",
                message="More than one TB1 row has this match key.",
            )
            blocked += 2
            continue
        if _publish_pair(tb1=tb1_candidates[0], tb2=tb2):
            published += 1
        else:
            blocked += 2
    return published, blocked


def _publish_pair(*, tb1: TB1RequestStagingRow, tb2: TB2SnapshotStagingRow) -> bool:
    """Link one exact pair and update the warehouse fact from the current TB2 snapshot.

    The fact's agency/reference unique constraint is the concurrency authority. If another worker
    wins the initial insert, retry in a fresh savepoint so this worker reloads and updates that fact
    instead of surfacing a duplicate-key failure to an operator.
    """

    for attempt in range(3):
        try:
            with transaction.atomic():
                tb2.matched_tb1 = tb1
                tb2.match_status = MatchStatus.MATCHED
                tb2.save(update_fields=["matched_tb1", "match_status"])
                if _is_older_than_current_tb2(tb1=tb1, tb2=tb2):
                    return True
                tb1.matched_tb2 = tb2
                tb1.match_status = MatchStatus.MATCHED
                tb1.save(update_fields=["matched_tb2", "match_status"])
                tb1_result = load_credit_request(
                    stage=tb1,
                    data=_tb1_warehouse_data(tb1),
                    source_kind=WorkbookKind.TB1,
                )
                tb2_result = load_credit_request(
                    stage=tb2,
                    data=_tb2_warehouse_data(tb1, tb2),
                    source_kind=WorkbookKind.TB2,
                )
        except IntegrityError:
            if attempt < 2:
                logger.info(
                    "Retrying concurrent warehouse publication for agency=%s reference=%s",
                    tb1.agency_id,
                    tb1.reference,
                )
                continue
            _block_pair(
                tb1=tb1,
                tb2_rows=[tb2],
                code="concurrent_publication_conflict",
                message=(
                    "Le dossier est en cours de mise à jour par un autre import. "
                    "Réimportez ce fichier dans quelques instants."
                ),
                field="reference",
            )
            return False
        except WarehouseLoadError as exc:
            _block_pair(tb1=tb1, tb2_rows=[tb2], code=exc.code, message=str(exc), field=exc.field)
            return False
        _create_warehouse_quality_issues(stage=tb1, result=tb1_result)
        _create_warehouse_quality_issues(stage=tb2, result=tb2_result)
        return True
    return False


def _is_older_than_current_tb2(*, tb1: TB1RequestStagingRow, tb2: TB2SnapshotStagingRow) -> bool:
    """Avoid regressing the fact when an older monthly TB2 snapshot is imported late."""

    if tb2.reporting_period is None:
        return False
    fact = (
        FactCreditRequest.objects.filter(current_tb1_row=tb1)
        .select_related("current_tb2_row")
        .first()
    )
    current_tb2 = fact.current_tb2_row if fact is not None else None
    return bool(
        current_tb2 is not None
        and current_tb2.reporting_period is not None
        and tb2.reporting_period < current_tb2.reporting_period
    )


def _supersede_prior_scopes(*, batch: ImportBatch) -> None:
    """Version staging rows independently for each agency/month/workbook scope.

    A consolidated TB2 workbook contains many agencies. Marking its entire predecessor batch as
    superseded would incorrectly hide unchanged agencies, so supersession is deliberately applied
    only to rows with the same resolved agency, reporting period, and typed source table.
    """

    stage_model: type[TB1RequestStagingRow] | type[TB2SnapshotStagingRow]
    stage_model = (
        TB1RequestStagingRow
        if batch.workbook_type == WorkbookKind.TB1.value
        else TB2SnapshotStagingRow
    )
    scopes = (
        stage_model.objects.filter(
            batch=batch,
            agency__isnull=False,
            reporting_period__isnull=False,
            validation_status=ValidationStatus.VALID,
        )
        .values_list("agency_id", "reporting_period")
        .distinct()
    )
    for agency_id, reporting_period in scopes:
        stage_model.objects.filter(
            agency_id=agency_id,
            reporting_period=reporting_period,
            is_current=True,
        ).exclude(batch=batch).update(is_current=False)


def _mark_absent_from_latest_tb2(*, batch: ImportBatch) -> None:
    """Flag facts absent from the newest accepted TB2 snapshot for each submitted agency.

    This is an operational completeness flag only: it never closes, rejects, or otherwise changes
    the dossier's derived business status. A late submission for an older period cannot overwrite
    the flag produced by a newer monthly submission.
    """

    if batch.workbook_type != WorkbookKind.TB2.value:
        return
    active_batch_statuses = [
        ImportBatch.Status.PROCESSING,
        ImportBatch.Status.COMPLETED,
        ImportBatch.Status.PARTIAL,
    ]
    scopes = (
        TB2SnapshotStagingRow.objects.filter(
            batch=batch,
            agency__isnull=False,
            reporting_period__isnull=False,
            validation_status=ValidationStatus.VALID,
            is_current=True,
        )
        .values_list("agency_id", "reporting_period")
        .distinct()
    )
    for agency_id, reporting_period in scopes:
        latest_period = TB2SnapshotStagingRow.objects.filter(
            agency_id=agency_id,
            reporting_period__isnull=False,
            validation_status=ValidationStatus.VALID,
            is_current=True,
            batch__status__in=active_batch_statuses,
        ).aggregate(latest=Max("reporting_period"))["latest"]
        if latest_period != reporting_period:
            continue
        submitted_references = TB2SnapshotStagingRow.objects.filter(
            batch=batch,
            agency_id=agency_id,
            reporting_period=reporting_period,
            validation_status=ValidationStatus.VALID,
            is_current=True,
        ).values_list("reference", flat=True)
        FactCreditRequest.objects.filter(
            agency_id=agency_id,
            reference__in=submitted_references,
        ).update(missing_from_latest_tb2_period=None)
        facts = FactCreditRequest.objects.filter(
            agency_id=agency_id,
            current_tb2_row__reporting_period__lt=reporting_period,
        )
        facts.exclude(reference__in=submitted_references).update(
            missing_from_latest_tb2_period=reporting_period
        )


def _tb1_warehouse_data(stage: TB1RequestStagingRow) -> dict[str, object]:
    """Build a warehouse payload without retaining client data in staging."""

    return {
        "reference": stage.reference,
        "amount": stage.amount,
        "request_date": stage.request_date,
        "credit_type": stage.credit_type_name,
        "request_type": stage.request_type_name,
        "activity_category": stage.activity_name,
    }


def _tb2_warehouse_data(tb1: TB1RequestStagingRow, tb2: TB2SnapshotStagingRow) -> dict[str, object]:
    return {
        **_tb1_warehouse_data(tb1),
        "gp_name": tb2.gp_name,
        "counsellor_name": tb2.ca_name,
        "received_at_agency_date": tb2.received_at_agency_date,
        "assigned_to_gp_date": tb2.assigned_to_gp_date,
        "visit_date": tb2.visit_date,
        "disbursement_date": tb2.disbursement_date,
        "rejection_date": tb2.rejection_date,
        "rejection_reason": tb2.rejection_reason,
        "amount_disbursed": tb2.amount,
    }


def _block_pair(
    *,
    tb1: TB1RequestStagingRow,
    tb2_rows: list[TB2SnapshotStagingRow],
    code: str,
    message: str,
    field: str = "",
) -> None:
    tb1.match_status = MatchStatus.BLOCKED
    tb1.save(update_fields=["match_status"])
    _create_pair_issue(stage=tb1, code=code, message=message, field=field)
    for tb2 in tb2_rows:
        tb2.match_status = MatchStatus.BLOCKED
        tb2.save(update_fields=["match_status"])
        _create_pair_issue(stage=tb2, code=code, message=message, field=field)


def _create_pair_issue(
    *,
    stage: TB1RequestStagingRow | TB2SnapshotStagingRow,
    code: str,
    message: str,
    field: str,
) -> None:
    row_lookup: dict[str, TB1RequestStagingRow | TB2SnapshotStagingRow | None] = {
        "tb1_row": stage if isinstance(stage, TB1RequestStagingRow) else None,
        "tb2_row": stage if isinstance(stage, TB2SnapshotStagingRow) else None,
    }
    DataQualityIssue.objects.get_or_create(
        batch=stage.batch,
        **row_lookup,
        severity=DataQualityIssue.Severity.ERROR,
        code=code,
        field_name=field,
        defaults={"message": message, "details": {}},
    )


def _create_warehouse_quality_issues(
    *,
    stage: TB1RequestStagingRow | TB2SnapshotStagingRow,
    result: WarehouseLoadResult,
) -> None:
    row_lookup: dict[str, object] = {"tb1_row": None, "tb2_row": None}
    if isinstance(stage, TB1RequestStagingRow):
        row_lookup["tb1_row"] = stage
    else:
        row_lookup["tb2_row"] = stage
    for issue in result.issues:
        DataQualityIssue.objects.get_or_create(
            batch=stage.batch,
            **row_lookup,
            code=issue.code,
            field_name=issue.field,
            defaults={
                "severity": DataQualityIssue.Severity.WARNING,
                "message": issue.message,
                "details": {},
            },
        )


def _stage_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _stage_decimal(
    value: object, *, max_digits: int = 18, decimal_places: int = 3
) -> Decimal | None:
    if not isinstance(value, Decimal) or not value.is_finite():
        return None
    maximum = Decimal(10) ** (max_digits - decimal_places) - Decimal(10) ** (-decimal_places)
    return value if abs(value) <= maximum else None


def _stage_date(value: object) -> date | None:
    return value if isinstance(value, date) else None


def _resolve_agency(
    raw_agency: str | None,
    cache: dict[tuple[str, str], AgencyDimension],
    *,
    source: AgencySource,
) -> AgencyDimension | None:
    if raw_agency is None:
        return None
    cleaned = re.sub(r"\s+", " ", raw_agency).strip()
    normalized = _normalize_agency_name(cleaned)
    if not normalized:
        return None
    cache_key = (normalized, source.value)
    if cache_key in cache:
        return cache[cache_key]

    matches = [
        agency
        for agency in AgencyDimension.objects.filter(is_active=True)
        if _normalize_agency_name(agency.name) == normalized
    ]
    if len(matches) > 1:
        return None
    if matches:
        agency = matches[0]
    else:
        return None
    cache[cache_key] = agency
    return agency


def _normalize_agency_name(value: str) -> str:
    return normalize_match_value(value)


def _employee_identity_issues(
    *,
    agency: AgencyDimension,
    data: Mapping[str, object],
    parsed_row: ParsedRow,
) -> tuple[ValidationIssue, ...]:
    """Require CA/GP values to resolve to one active employee in the row agency."""

    checks: tuple[tuple[str, str, type[CADimension] | type[GPDimension], str], ...] = (
        ("counsellor_name", "CA/CAA", CADimension, "counsellor_name"),
        ("gp_name", "GP", GPDimension, "gp_name"),
    )
    issues: list[ValidationIssue] = []
    for key, role, model, field in checks:
        required_date_field = (
            "received_at_agency_date" if key == "counsellor_name" else "assigned_to_gp_date"
        )
        if not isinstance(data.get(required_date_field), date):
            continue
        raw_value = data.get(key)
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        if not value:
            code = "missing_employee_identity"
            message = (
                f"A {role} name is required and must match an active {role} employee in the agency."
            )
        else:
            normalized = normalize_match_value(value)
            matches = [
                employee
                for employee in model.objects.filter(agency=agency, is_active=True)
                if normalize_match_value(employee.name) == normalized
            ]
            if normalized != normalize_match_value("Inconnu") and len(matches) == 1:
                continue
            code = "unresolved_employee_identity"
            message = (
                f"The {role} name must match exactly one active {role} employee in the agency."
            )
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity=IssueSeverity.ERROR,
                field=field,
                sheet_name=parsed_row.sheet_name,
                row_number=parsed_row.source_row,
            )
        )
    return tuple(issues)


def _governed_reference_issues(
    *,
    agency: AgencyDimension,
    data: Mapping[str, object],
    parsed_row: ParsedRow,
) -> tuple[ValidationIssue, ...]:
    """Validate that the reference belongs to the resolved agency."""

    reference = data.get("reference")
    try:
        parsed_reference = parse_canonical_reference(reference)
    except CellValueError:
        # The parser has already added the structural, date, and Excel-type issue.
        return ()

    issues: list[ValidationIssue] = []
    if not agency.code:
        message = "Cette agence n\u2019a pas encore de code de référence configuré."
    elif parsed_reference.agency_code != agency.code:
        message = "Le code agence de la référence ne correspond pas à l\u2019agence résolue."
    else:
        message = ""
    if message:
        issues.append(
            ValidationIssue(
                code="reference_agency_code_mismatch",
                message=message,
                severity=IssueSeverity.ERROR,
                field="reference",
                sheet_name=parsed_row.sheet_name,
                row_number=parsed_row.source_row,
            )
        )

    return tuple(issues)


def _governed_dimension_issues(
    *,
    data: Mapping[str, object],
    source_kind: WorkbookKind,
    parsed_row: ParsedRow,
) -> tuple[ValidationIssue, ...]:
    """Reject values that do not resolve to one active governed dimension."""

    checks: tuple[
        tuple[
            str,
            type[CreditTypeDimension]
            | type[ActivityDimension]
            | type[RequestTypeDimension]
            | type[StatusDimension]
            | type[RejectionReasonDimension],
        ],
        ...,
    ]
    if source_kind is WorkbookKind.TB1:
        checks = (
            ("credit_type", CreditTypeDimension),
            ("activity_category", ActivityDimension),
            ("request_type", RequestTypeDimension),
        )
    else:
        checks = (
            ("request_type", RequestTypeDimension),
            ("status", StatusDimension),
            ("rejection_reason", RejectionReasonDimension),
        )
    issues: list[ValidationIssue] = []
    for field_name, model in checks:
        raw_value = data.get(field_name)
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        if not value:
            continue
        normalized = normalize_match_value(value)
        matches = [
            dimension
            for dimension in model.objects.filter(is_active=True)
            if normalize_match_value(dimension.name) == normalized
        ]
        if len(matches) == 1:
            continue
        issues.append(
            ValidationIssue(
                code="unresolved_dimension_value",
                message="The value must match exactly one active reference-data entry.",
                severity=IssueSeverity.ERROR,
                field=field_name,
                sheet_name=parsed_row.sheet_name,
                row_number=parsed_row.source_row,
            )
        )
    return tuple(issues)


def _json_ready_mapping(values: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values.items():
        if isinstance(value, Decimal):
            result[key] = format(value, "f")
        elif isinstance(value, date):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _row_fingerprint(row: ParsedRow) -> str:
    payload = {
        "sheet": row.sheet_name,
        "row": row.source_row,
        "raw": row.raw_data,
        "normalized": _json_ready_mapping(row.data),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _deduplicate_issues(issues: list[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    unique: dict[tuple[str, str | None], ValidationIssue] = {}
    for issue in issues:
        unique.setdefault((issue.code, issue.field), issue)
    return tuple(unique.values())


def _template_rule_issue(
    *,
    code: str,
    message: str,
    parsed_row: ParsedRow,
    field: str,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        severity=IssueSeverity.ERROR,
        field=field,
        sheet_name=parsed_row.sheet_name,
        row_number=parsed_row.source_row,
    )


def _create_quality_issue(
    *,
    batch: ImportBatch,
    row: TB1RequestStagingRow | TB2SnapshotStagingRow | None,
    issue: ValidationIssue,
    parsed_row: ParsedRow | None = None,
    source_kind: WorkbookKind | None = None,
) -> None:
    severity = {
        IssueSeverity.WARNING: DataQualityIssue.Severity.WARNING,
        IssueSeverity.ERROR: DataQualityIssue.Severity.ERROR,
    }[issue.severity]
    row_lookup: dict[str, object] = {"tb1_row": None, "tb2_row": None}
    if isinstance(row, TB1RequestStagingRow):
        row_lookup["tb1_row"] = row
    elif isinstance(row, TB2SnapshotStagingRow):
        row_lookup["tb2_row"] = row
    details: dict[str, object] = {
        "row_number": issue.row_number,
        "column_number": issue.column_number,
    }
    submitted_value = _safe_submitted_issue_value(parsed_row, issue.field)
    if submitted_value is not None:
        details["submitted_value"] = submitted_value
    if row is None and parsed_row is not None and source_kind is not None:
        details.update(
            {
                "sheet_name": parsed_row.sheet_name,
                "source_row": parsed_row.source_row,
                "source_kind": source_kind.value,
                "row_values": _correction_values(parsed_row, source_kind),
            }
        )
        # No staging row exists for a rejected workbook.  Keep every row-level
        # issue rather than collapsing same-code issues from different rows.
        DataQualityIssue.objects.create(
            batch=batch,
            **row_lookup,
            severity=severity,
            code=issue.code,
            field_name=issue.field or "",
            message=issue.message,
            details=details,
        )
        return
    DataQualityIssue.objects.get_or_create(
        batch=batch,
        **row_lookup,
        code=issue.code,
        field_name=issue.field or "",
        defaults={
            "severity": severity,
            "message": issue.message,
            "details": details,
        },
    )


def _safe_submitted_issue_value(parsed_row: ParsedRow | None, field_name: str | None) -> str | None:
    """Retain a bounded correction value only for governed non-client fields."""

    if parsed_row is None or field_name not in VISIBLE_ISSUE_VALUE_FIELDS:
        return None
    for headers in TEMPLATE_HEADERS.values():
        for header, canonical_field in headers.items():
            if canonical_field == field_name and header in parsed_row.raw_data:
                value = parsed_row.raw_data[header]
                if value is None or (isinstance(value, str) and not value.strip()):
                    return ""
                return str(value).strip()[:200]
    return None


def _correction_values(parsed_row: ParsedRow, source_kind: WorkbookKind) -> dict[str, object]:
    """Build the safe full-row projection used by the correction UI."""

    values: dict[str, object] = {}
    for header, field_name in TEMPLATE_HEADERS[source_kind].items():
        if field_name not in VISIBLE_ISSUE_VALUE_FIELDS:
            continue
        value = parsed_row.raw_data.get(header)
        if isinstance(value, str):
            value = value.strip()[:200]
        values[field_name] = value
    return values


def _failure_code(exc: WorkbookParserError) -> str:
    name = exc.__class__.__name__.removesuffix("Error")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()[:64]


def _sanitized_failure_message(exc: WorkbookParserError) -> str:
    """Return a stable failure summary that cannot echo workbook-controlled text."""

    if isinstance(exc, AgencyScopeViolationError | ReplayRequiresReconciliationError):
        return str(exc)
    if isinstance(exc, WorkbookLimitError):
        return "The workbook exceeds a configured processing limit."
    if isinstance(exc, InvalidWorkbookError):
        return "The supplied workbook is not a readable XLSX file."
    if isinstance(exc, UnsupportedWorkbookError):
        return "The workbook does not contain a supported TB1 or TB2 schema."
    if isinstance(exc, ParserConfigurationError):
        return "The import parser configuration is invalid."
    return "The workbook could not be processed safely."


def _mark_failed(batch_id: Any, _code: str, message: str) -> dict[str, int | str]:
    with transaction.atomic():
        batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
        if batch.status in TERMINAL_IMPORT_STATUSES:
            return _batch_summary(batch)
        batch.status = ImportBatch.Status.FAILED
        batch.error_message = message[:2000]
        batch.finished_at = timezone.now()
        batch.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        return _batch_summary(batch)


def _batch_summary(batch: ImportBatch) -> dict[str, int | str]:
    return {
        "batch_id": str(batch.pk),
        "status": batch.status,
        "rows_discovered": batch.rows_discovered,
        "rows_imported": batch.rows_imported,
        "rows_rejected": batch.rows_rejected,
    }
