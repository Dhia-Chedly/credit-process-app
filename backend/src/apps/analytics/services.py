from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Any
from uuid import UUID

from django.db.models import F, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.imports.models import (
    ImportBatch,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
)
from apps.warehouse.models import (
    AgencyDimension,
    CADimension,
    FactCreditRequest,
    GPDimension,
    StatusDimension,
)


@dataclass(frozen=True, slots=True)
class AnalyticsFilters:
    """Validated cohort filters plus the caller's enforced row-level scope."""

    date_from: date
    date_to: date
    agency_ids: tuple[UUID, ...]
    ca_id: UUID | None = None
    gp_id: UUID | None = None
    employee_id: UUID | None = None
    employee_role: str | None = None
    mask_employee_names: bool = True

    @classmethod
    def from_validated(
        cls,
        values: Mapping[str, object],
        *,
        user: Any,
    ) -> AnalyticsFilters:
        requested_agencies = values.get("agency")
        agency_ids = (
            tuple(value for value in requested_agencies if isinstance(value, UUID))
            if isinstance(requested_agencies, tuple)
            else ()
        )
        requested_ca = values.get("ca")
        ca_id = requested_ca if isinstance(requested_ca, UUID) else None
        requested_gp = values.get("gp")
        gp_id = requested_gp if isinstance(requested_gp, UUID) else None
        employee_id: UUID | None = None
        employee_role: str | None = None
        raw_from = values.get("date_from")
        raw_to = values.get("date_to")
        current_month = _month_start(timezone.localdate())
        requested_to = _month_start(raw_to) if isinstance(raw_to, date) else current_month
        date_to = min(requested_to, current_month)
        date_from = (
            _month_start(raw_from) if isinstance(raw_from, date) else _add_months(date_to, -11)
        )
        if date_from > date_to:
            raise ValidationError({"date_from": "The analytics window cannot start in the future."})

        mask_names = not bool(getattr(user, "is_authenticated", False))
        return cls(
            date_from=date_from,
            date_to=date_to,
            agency_ids=agency_ids,
            ca_id=ca_id,
            gp_id=gp_id,
            employee_id=employee_id,
            employee_role=employee_role,
            mask_employee_names=mask_names,
        )

    def as_payload(self) -> dict[str, str | None]:
        return {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "agency": ",".join(str(agency_id) for agency_id in self.agency_ids) or None,
            "ca": str(self.ca_id) if self.ca_id else None,
            "gp": str(self.gp_id) if self.gp_id else None,
            "grain": "request_month",
            "row_scope": "assigned_requests" if self.employee_id else "agency_or_network",
        }


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _window_end(filters: AnalyticsFilters) -> date:
    return _add_months(filters.date_to, 1)


def _expected_month_count(filters: AnalyticsFilters) -> int:
    return (
        (filters.date_to.year - filters.date_from.year) * 12
        + filters.date_to.month
        - filters.date_from.month
        + 1
    )


def _fact_queryset(filters: AnalyticsFilters) -> QuerySet[FactCreditRequest]:
    today = timezone.localdate()
    queryset = FactCreditRequest.objects.filter(
        current_tb1_row__isnull=False,
        current_tb2_row__isnull=False,
        request_date__calendar_date__gte=filters.date_from,
        request_date__calendar_date__lt=_window_end(filters),
        request_date__calendar_date__lte=today,
    )
    if filters.agency_ids:
        queryset = queryset.filter(agency_id__in=filters.agency_ids)
    if filters.ca_id is not None:
        queryset = queryset.filter(ca_caa_id=filters.ca_id)
    if filters.gp_id is not None:
        queryset = queryset.filter(gp_id=filters.gp_id)
    if filters.employee_id is not None:
        if filters.employee_role == "gp":
            queryset = queryset.filter(gp_id=filters.employee_id)
        else:
            queryset = queryset.none()
    return queryset


FACT_VALUE_FIELDS = (
    "id",
    "agency_id",
    "agency__name",
    "gp_id",
    "gp__name",
    "ca_caa_id",
    "ca_caa__name",
    "activity__name",
    "credit_type__name",
    "request_type__name",
    "rejection_reason__name",
    "status__code",
    "status__name",
    "status__pipeline_stage",
    "status__is_terminal",
    "amount",
    "request_date__calendar_date",
    "reception_date__calendar_date",
    "gp_assignment_date__calendar_date",
    "visit_date__calendar_date",
    "disbursement_date__calendar_date",
    "rejection_date__calendar_date",
    "current_tb1_row__batch__status",
    "current_tb2_row__batch__status",
)


def _fact_rows(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    rows = list(_fact_queryset(filters).values(*FACT_VALUE_FIELDS))
    for row in rows:
        status_code = row.get("status__code")
        funded = status_code == "funded"
        rejected = status_code == "rejected"
        row.update(
            requested_amount=row.get("amount"),
            disbursed_amount=row.get("amount") if funded else None,
            has_tb1=True,
            has_tb2=True,
            is_funded=funded,
            is_rejected=rejected,
            is_open=not (funded or rejected),
        )
    return rows


def _is_registered(_row: Mapping[str, Any]) -> bool:
    return True


def _is_funded_request(row: Mapping[str, Any]) -> bool:
    return _is_registered(row) and bool(row.get("is_funded"))


def _is_rejected_request(row: Mapping[str, Any]) -> bool:
    return _is_registered(row) and bool(row.get("is_rejected"))


def _is_matched_request(_row: Mapping[str, Any]) -> bool:
    return True


def _is_terminal_request(row: Mapping[str, Any]) -> bool:
    return _is_registered(row) and (
        bool(row.get("status__is_terminal"))
        or bool(row.get("is_funded"))
        or bool(row.get("is_rejected"))
    )


def _row_is_provisional(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("current_tb1_row__batch__status") == ImportBatch.Status.PARTIAL
        or row.get("current_tb2_row__batch__status") == ImportBatch.Status.PARTIAL
    )


def _valid_days(start: date | None, end: date | None) -> int | None:
    today = timezone.localdate()
    if start is None or end is None or start > end or start > today or end > today:
        return None
    days = (end - start).days
    return days if days <= 365 else None


def _outcome_date(row: Mapping[str, Any]) -> date | None:
    return (
        row.get("disbursement_date__calendar_date")
        or row.get("rejection_date__calendar_date")
        or row.get("outcome_date__calendar_date")
    )


def _sum_amount(rows: Iterable[Mapping[str, Any]], key: str) -> float:
    return float(sum((row.get(key) or Decimal("0")) for row in rows))


def _average(values: Iterable[int]) -> float | None:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 2) if materialized else None


def _as_int(value: object) -> int:
    if isinstance(value, bool | int | float | Decimal | str):
        return int(value)
    return 0


@dataclass(slots=True)
class SourceStats:
    tb1_submitted: set[tuple[str, date]]
    tb2_submitted: set[tuple[str, date]]
    tb1_usable: set[tuple[str, date]]
    tb2_usable: set[tuple[str, date]]
    provisional: set[tuple[str, date]]
    tb1_committed_rows: int
    tb1_quarantined_rows: int
    tb2_committed_rows: int
    tb2_quarantined_rows: int
    partial_batches: int


def _source_stats(filters: AnalyticsFilters) -> SourceStats:
    if filters.employee_id is not None:
        return _assigned_source_stats(filters)

    batch_query = ImportBatch.objects.filter(
        workbook_type__in=[ImportBatch.WorkbookType.TB1, ImportBatch.WorkbookType.TB2],
        status__in=[ImportBatch.Status.COMPLETED, ImportBatch.Status.PARTIAL],
        reporting_period__gte=filters.date_from,
        reporting_period__lt=_window_end(filters),
        detected_agency__isnull=False,
    )
    if filters.agency_ids:
        batch_query = batch_query.filter(detected_agency_id__in=filters.agency_ids)
    batch_rows = list(
        batch_query.values(
            "id", "workbook_type", "status", "detected_agency_id", "reporting_period"
        )
    )
    tb1_submitted: set[tuple[str, date]] = set()
    tb2_submitted: set[tuple[str, date]] = set()
    provisional: set[tuple[str, date]] = set()
    partial_batch_ids = {
        str(batch["id"]) for batch in batch_rows if batch["status"] == ImportBatch.Status.PARTIAL
    }
    for batch in batch_rows:
        period = batch["reporting_period"]
        agency_id = batch["detected_agency_id"]
        if not isinstance(period, date) or agency_id is None:
            continue
        key = (str(agency_id), _month_start(period))
        if batch["workbook_type"] == ImportBatch.WorkbookType.TB1:
            tb1_submitted.add(key)
        else:
            tb2_submitted.add(key)
        if batch["status"] == ImportBatch.Status.PARTIAL:
            provisional.add(key)

    tb1_rows = _typed_rows(TB1RequestStagingRow, filters)
    tb2_rows = _typed_rows(TB2SnapshotStagingRow, filters)
    tb1_committed: set[tuple[str, date]] = set()
    tb2_committed: set[tuple[str, date]] = set()
    tb1_quarantined = 0
    tb2_quarantined = 0
    tb1_committed_count = 0
    tb2_committed_count = 0
    for row in tb1_rows:
        stage_key = _row_period_key(row)
        if stage_key:
            tb1_submitted.add(stage_key)
            if row["batch__status"] == ImportBatch.Status.PARTIAL:
                partial_batch_ids.add(str(row["batch_id"]))
                provisional.add(stage_key)
        if row["validation_status"] == "valid" and row["match_status"] == "matched":
            tb1_committed_count += 1
            if stage_key:
                tb1_committed.add(stage_key)
        elif row["validation_status"] == "invalid" or row["match_status"] == "blocked":
            tb1_quarantined += 1
            if stage_key:
                provisional.add(stage_key)
    for row in tb2_rows:
        stage_key = _row_period_key(row)
        if stage_key:
            tb2_submitted.add(stage_key)
            if row["batch__status"] == ImportBatch.Status.PARTIAL:
                partial_batch_ids.add(str(row["batch_id"]))
                provisional.add(stage_key)
        if row["validation_status"] == "valid" and row["match_status"] == "matched":
            tb2_committed_count += 1
            if stage_key:
                tb2_committed.add(stage_key)
        elif row["validation_status"] == "invalid" or row["match_status"] == "blocked":
            tb2_quarantined += 1
            if stage_key:
                provisional.add(stage_key)
    return SourceStats(
        tb1_submitted=tb1_submitted,
        tb2_submitted=tb2_submitted,
        tb1_usable={key for key in tb1_committed & tb1_submitted if key not in provisional},
        tb2_usable={key for key in tb2_committed & tb2_submitted if key not in provisional},
        provisional=provisional,
        tb1_committed_rows=tb1_committed_count,
        tb1_quarantined_rows=tb1_quarantined,
        tb2_committed_rows=tb2_committed_count,
        tb2_quarantined_rows=tb2_quarantined,
        partial_batches=len(partial_batch_ids),
    )


def _assigned_source_stats(filters: AnalyticsFilters) -> SourceStats:
    """Return only provenance linked to facts in an employee's exact row scope.

    Quarantined rows and unrelated agency batches cannot be attributed to an
    employee, so they must not be counted in an assigned-request response.
    """

    fields: list[str] = []
    for prefix in ("current_tb1_row", "current_tb2_row"):
        fields.extend(
            (
                f"{prefix}_id",
                f"{prefix}__validation_status",
                f"{prefix}__match_status",
                f"{prefix}__batch_id",
                f"{prefix}__batch__reporting_period",
                f"{prefix}__batch__status",
            )
        )
    fields.extend(("agency_id", "tb1_reporting_period", "tb2_reporting_period"))
    rows = list(_fact_queryset(filters).values(*fields))

    submitted: dict[str, set[tuple[str, date]]] = {"tb1": set(), "tb2": set()}
    usable: dict[str, set[tuple[str, date]]] = {"tb1": set(), "tb2": set()}
    committed_rows = {"tb1": 0, "tb2": 0}
    quarantined_rows = {"tb1": 0, "tb2": 0}
    seen_rows: dict[str, set[object]] = {"tb1": set(), "tb2": set()}
    provisional: set[tuple[str, date]] = set()
    partial_batch_ids: set[str] = set()

    for row in rows:
        for kind in ("tb1", "tb2"):
            prefix = f"current_{kind}_row"
            row_id = row.get(f"{prefix}_id")
            if row_id is None or row_id in seen_rows[kind]:
                continue
            seen_rows[kind].add(row_id)
            period = row.get(f"{prefix}__batch__reporting_period") or row.get(
                f"{kind}_reporting_period"
            )
            agency_id = row.get("agency_id")
            key = (
                (str(agency_id), _month_start(period))
                if agency_id is not None and isinstance(period, date)
                else None
            )
            if key is not None:
                submitted[kind].add(key)

            validation_status = row.get(f"{prefix}__validation_status")
            match_status = row.get(f"{prefix}__match_status")
            batch_status = row.get(f"{prefix}__batch__status")
            if validation_status == "valid" and match_status == "matched":
                committed_rows[kind] += 1
                if key is not None and batch_status != ImportBatch.Status.PARTIAL:
                    usable[kind].add(key)
            elif validation_status == "invalid" or match_status == "blocked":
                quarantined_rows[kind] += 1

            if key is not None and (
                validation_status != "valid"
                or match_status != "matched"
                or batch_status == ImportBatch.Status.PARTIAL
            ):
                provisional.add(key)
            if batch_status == ImportBatch.Status.PARTIAL:
                batch_id = row.get(f"{prefix}__batch_id")
                if batch_id is not None:
                    partial_batch_ids.add(str(batch_id))

    return SourceStats(
        tb1_submitted=submitted["tb1"],
        tb2_submitted=submitted["tb2"],
        tb1_usable=usable["tb1"],
        tb2_usable=usable["tb2"],
        provisional=provisional,
        tb1_committed_rows=committed_rows["tb1"],
        tb1_quarantined_rows=quarantined_rows["tb1"],
        tb2_committed_rows=committed_rows["tb2"],
        tb2_quarantined_rows=quarantined_rows["tb2"],
        partial_batches=len(partial_batch_ids),
    )


def _typed_rows(model: Any, filters: AnalyticsFilters) -> list[dict[str, Any]]:
    query = model.objects.annotate(source_period=F("batch__reporting_period")).filter(
        source_period__gte=filters.date_from,
        source_period__lt=_window_end(filters),
    )
    if filters.agency_ids:
        query = query.filter(batch__detected_agency_id__in=filters.agency_ids)
    return list(
        query.values(
            "validation_status",
            "match_status",
            "batch__detected_agency_id",
            "source_period",
            "batch_id",
            "batch__status",
        )
    )


def _row_period_key(row: Mapping[str, Any]) -> tuple[str, date] | None:
    period = row.get("source_period")
    agency_id = row.get("batch__detected_agency_id")
    if not isinstance(period, date) or agency_id is None:
        return None
    return str(agency_id), _month_start(period)


def _agency_catalog(filters: AnalyticsFilters) -> dict[str, dict[str, Any]]:
    # Inactive agencies remain part of historical facts and must remain visible in analytics.
    query = AgencyDimension.objects.all()
    if filters.agency_ids:
        query = query.filter(id__in=filters.agency_ids)
    return {str(row["id"]): dict(row) for row in query.values("id", "name")}


def _coverage_by_agency(
    filters: AnalyticsFilters, stats: SourceStats | None = None
) -> dict[str, dict[str, int | float | bool | None]]:
    stats = stats or _source_stats(filters)
    expected = _expected_month_count(filters)
    agency_ids = set(_agency_catalog(filters))
    agency_ids.update(key[0] for key in stats.tb1_submitted | stats.tb2_submitted)
    result: dict[str, dict[str, int | float | bool | None]] = {}
    for agency_id in agency_ids:
        tb1_submitted = sum(key[0] == agency_id for key in stats.tb1_submitted)
        tb1_usable = sum(key[0] == agency_id for key in stats.tb1_usable)
        tb2_submitted = sum(key[0] == agency_id for key in stats.tb2_submitted)
        provisional_months = sum(key[0] == agency_id for key in stats.provisional)
        result[agency_id] = {
            "expected_months": expected,
            "tb1_submitted_months": tb1_submitted,
            "tb1_usable_months": tb1_usable,
            "tb1_unusable_submitted_months": max(tb1_submitted - tb1_usable, 0),
            "missing_tb1_months": max(expected - tb1_submitted, 0),
            "tb2_submitted_months": tb2_submitted,
            "provisional_source_months": provisional_months,
            "tb1_submission_coverage_rate": (
                round(100.0 * tb1_submitted / expected, 2) if expected else None
            ),
            "tb1_usable_coverage_rate": (
                round(100.0 * tb1_usable / expected, 2) if expected else None
            ),
            "ranking_eligible": bool(expected and tb1_usable == expected),
        }
    return result


def completeness(filters: AnalyticsFilters) -> dict[str, object]:
    rows = _fact_rows(filters)
    registered = [row for row in rows if _is_registered(row)]
    funded = [row for row in rows if _is_funded_request(row)]
    matched = [row for row in rows if _is_matched_request(row)]
    tb2_only: list[dict[str, Any]] = []
    date_anomalies = sum(_has_date_anomaly(row) for row in registered)
    future_milestones = sum(_has_future_milestone(row) for row in registered)
    stats = _source_stats(filters)
    coverage = _coverage_by_agency(filters, stats)
    expected_agency_months = sum(_as_int(item["expected_months"]) for item in coverage.values())
    submitted_months = sum(_as_int(item["tb1_submitted_months"]) for item in coverage.values())
    usable_months = sum(_as_int(item["tb1_usable_months"]) for item in coverage.values())
    unusable_months = sum(
        _as_int(item["tb1_unusable_submitted_months"]) for item in coverage.values()
    )
    missing_months = sum(_as_int(item["missing_tb1_months"]) for item in coverage.values())
    observed_agencies = {str(row["agency_id"]) for row in rows}
    matched_without_funded = sum(not _is_funded_request(row) for row in matched)
    limitations: list[dict[str, str]] = []

    def limit(code: str, message: str, condition: object) -> None:
        if condition:
            limitations.append({"code": code, "message": message})

    limit("no_data", "No lifecycle facts match these filters.", not rows)
    limit(
        "tb2_without_tb1",
        "Some TB2 portfolio observations have no registered TB1 request.",
        tb2_only,
    )
    limit(
        "tb2_match_without_financed_status",
        "Some TB1/TB2 matches are not currently confirmed as funded.",
        matched_without_funded,
    )
    limit("date_anomalies", "Some lifecycle milestones are not chronological.", date_anomalies)
    limit(
        "future_milestone_dates",
        "Some lifecycle milestones are later than today's business date.",
        future_milestones,
    )
    limit(
        "missing_disbursement_dates",
        "Some funded requests cannot contribute to disbursement-delay metrics.",
        any(row.get("disbursement_date__calendar_date") is None for row in funded),
    )
    limit(
        "activity_taxonomy_incomplete",
        "Unmapped activity labels remain staging-only and are excluded from rankings.",
        any(row.get("activity__name") is None for row in registered),
    )
    limit(
        "employee_identity_unresolved",
        "Some requests have no governed GP identity and are excluded from employee ranking.",
        any(row.get("gp_id") is None for row in registered),
    )
    limit(
        "counsellor_data_unavailable",
        "Some requests have no governed CA/CAA assignment.",
        any(row.get("ca_caa_id") is None for row in registered),
    )
    limit(
        "missing_tb1_agency_months",
        "Some expected agency-months have no TB1 submission; zero demand is not inferred.",
        missing_months,
    )
    limit(
        "unusable_tb1_agency_months",
        "Partial or quarantined TB1 months remain provisional and outside demand ranking.",
        unusable_months,
    )
    limit(
        "quarantined_staging_rows",
        "Quarantined typed staging rows never enter dimensions or facts.",
        stats.tb1_quarantined_rows or stats.tb2_quarantined_rows,
    )

    has_tb1 = bool(registered)
    has_tb2 = bool(rows)
    source_coverage = (
        "both"
        if has_tb1 and has_tb2
        else "tb1_only"
        if has_tb1
        else "tb2_only"
        if has_tb2
        else "none"
    )
    return {
        "provisional": bool(limitations),
        "observed_records": len(rows),
        "registered_requests": len(registered),
        "tb2_only_observations": len(tb2_only),
        "funded_requests": len(funded),
        "matched_requests": len(matched),
        "matched_without_financed_status": matched_without_funded,
        "date_anomaly_records": date_anomalies,
        "future_request_date_records": _future_request_count(filters),
        "future_milestone_date_records": future_milestones,
        "delay_eligible_funded_requests": sum(
            row.get("disbursement_date__calendar_date") is not None for row in funded
        ),
        "disbursed_amount_sample_size": sum(
            row.get("disbursed_amount") is not None for row in funded
        ),
        "controlled_activity_records": sum(
            row.get("activity__name") is not None for row in registered
        ),
        "gp_label_records": sum(row.get("gp_id") is not None for row in registered),
        "counsellor_label_records": sum(row.get("ca_caa_id") is not None for row in registered),
        "source_coverage": source_coverage,
        "source_completeness_scope": (
            "assigned_current_provenance"
            if filters.employee_id is not None
            else "agency_or_network_sources"
        ),
        "has_tb1_data": has_tb1,
        "has_tb2_data": has_tb2,
        "active_agency_count": len(coverage),
        "observed_agency_count": len(observed_agencies),
        "mapped_observed_agency_count": 0,
        "agencies_without_observed_data": max(len(coverage) - len(observed_agencies), 0),
        "expected_agency_months": expected_agency_months,
        "tb1_submitted_agency_months": submitted_months,
        "tb1_usable_agency_months": usable_months,
        "tb1_unusable_submitted_agency_months": unusable_months,
        "missing_tb1_agency_months": missing_months,
        "tb1_submission_coverage_rate": (
            round(100.0 * submitted_months / expected_agency_months, 2)
            if expected_agency_months
            else None
        ),
        "tb1_usable_coverage_rate": (
            round(100.0 * usable_months / expected_agency_months, 2)
            if expected_agency_months
            else None
        ),
        "typed_staging": {
            "tb1": {
                "committed_rows": stats.tb1_committed_rows,
                "quarantined_rows": stats.tb1_quarantined_rows,
                "submitted_agency_months": len(stats.tb1_submitted),
                "usable_agency_months": len(stats.tb1_usable),
            },
            "tb2": {
                "committed_rows": stats.tb2_committed_rows,
                "quarantined_rows": stats.tb2_quarantined_rows,
                "submitted_agency_months": len(stats.tb2_submitted),
                "usable_agency_months": len(stats.tb2_usable),
            },
            "partial_batches": stats.partial_batches,
        },
        "limitations": limitations,
    }


def _future_request_count(filters: AnalyticsFilters) -> int:
    query = FactCreditRequest.objects.filter(
        current_tb1_row__isnull=False,
        current_tb2_row__isnull=False,
        request_date__calendar_date__gt=timezone.localdate(),
    )
    if filters.agency_ids:
        query = query.filter(agency_id__in=filters.agency_ids)
    if filters.employee_id is not None:
        if filters.employee_role == "gp":
            query = query.filter(gp_id=filters.employee_id)
        else:
            return 0
    return query.count()


def _has_date_anomaly(row: Mapping[str, Any]) -> bool:
    dates = [
        row.get("request_date__calendar_date"),
        row.get("reception_date__calendar_date"),
        row.get("gp_assignment_date__calendar_date"),
        row.get("visit_date__calendar_date"),
        _outcome_date(row),
    ]
    materialized = [value for value in dates if isinstance(value, date)]
    return any(second < first for first, second in pairwise(materialized))


def _has_future_milestone(row: Mapping[str, Any]) -> bool:
    today = timezone.localdate()
    return any(
        isinstance(value, date) and value > today
        for key, value in row.items()
        if key.endswith("_date__calendar_date")
    )


def metadata(filters: AnalyticsFilters) -> dict[str, object]:
    catalog = _agency_catalog(filters)
    rows = _fact_rows(filters)
    dates = [
        row["request_date__calendar_date"]
        for row in rows
        if isinstance(row.get("request_date__calendar_date"), date)
    ]
    statuses = list(
        StatusDimension.objects.filter(is_active=True)
        .order_by("name")
        .values("code", "name", "pipeline_stage", "is_terminal", "is_funded", "is_rejected")
    )

    def staff_options(
        model: type[CADimension] | type[GPDimension], role: str
    ) -> list[dict[str, object]]:
        # Keep inactive employees available as historical filter values. Inactivity only governs
        # new imports; excluding them here would make their existing dossiers disappear from views.
        queryset = model.objects.select_related("agency")
        if filters.agency_ids:
            queryset = queryset.filter(agency_id__in=filters.agency_ids)
        options = [
            {
                "id": str(staff.pk),
                "display_name": staff.name,
                "role": role,
                "agency_id": str(staff.agency_id),
                "identity_status": "controlled",
            }
            for staff in queryset.order_by("name")
        ]
        return sorted(options, key=lambda item: str(item["display_name"]).casefold())

    return {
        "date_range": {
            "minimum": min(dates).isoformat() if dates else None,
            "maximum": max(dates).isoformat() if dates else None,
        },
        "agencies": [
            {
                "agency_id": agency_id,
                "name": item["name"],
                "has_data": any(str(row["agency_id"]) == agency_id for row in rows),
            }
            for agency_id, item in sorted(catalog.items(), key=lambda pair: str(pair[1]["name"]))
        ],
        "statuses": statuses,
        "intervals": [{"code": code, "label": label} for code, label, *_ in INTERVALS],
        "employee_roles": [
            {"code": "gp", "label": "Portfolio manager (GP)"},
            {"code": "ca", "label": "Counsellor (CA/CAA)"},
        ],
        "employees": {
            "gp": staff_options(GPDimension, "gp"),
            "ca": staff_options(CADimension, "ca"),
        },
        "definitions": {
            "total_requests": "Lifecycle facts with committed TB1 provenance.",
            "funded_requests": "TB1 requests whose current TB2-controlled outcome is funded.",
            "matched_requests": "TB1 requests with current TB2 provenance.",
            "nonfunded_requests": "TB1 requests not currently confirmed funded.",
            "portfolio_observations": "Lifecycle facts with current TB2 provenance.",
            "tb2_only_observations": "TB2 facts without committed TB1 provenance.",
            "processing_delay": "Calendar days between governed lifecycle dates, capped at 365.",
            "request_fact_precedence": (
                "Latest accepted TB1 controls request facts; latest accepted TB2 controls "
                "lifecycle outcomes."
            ),
        },
        "completeness": completeness(filters),
    }


def overview(filters: AnalyticsFilters) -> dict[str, object]:
    rows = _fact_rows(filters)
    registered = [row for row in rows if _is_registered(row)]
    funded = [row for row in rows if _is_funded_request(row)]
    rejected = [row for row in rows if _is_rejected_request(row)]
    matched = [row for row in rows if _is_matched_request(row)]
    processing_days = [
        duration
        for row in registered
        if _is_terminal_request(row)
        and (duration := _valid_days(row.get("request_date__calendar_date"), _outcome_date(row)))
        is not None
    ]
    disbursement_days = [
        duration
        for row in funded
        if (
            duration := _valid_days(
                row.get("request_date__calendar_date"),
                row.get("disbursement_date__calendar_date"),
            )
        )
        is not None
    ]
    total = len(registered)
    return {
        "observed_records": len(rows),
        "total_requests": total,
        "funded_requests": len(funded),
        "nonfunded_requests": total - len(funded),
        "rejected_requests": len(rejected),
        "open_or_unknown_requests": sum(
            not _is_funded_request(row) and not _is_rejected_request(row) for row in registered
        ),
        "active_requests": sum(bool(row.get("is_open")) for row in registered),
        "matched_requests": len(matched),
        "matched_without_financed_status": sum(not _is_funded_request(row) for row in matched),
        "portfolio_observations": len(rows),
        "requested_amount": _sum_amount(registered, "requested_amount"),
        "disbursed_amount": _sum_amount(
            (row for row in funded if row.get("disbursed_amount") is not None),
            "disbursed_amount",
        ),
        "disbursed_amount_sample_size": sum(
            row.get("disbursed_amount") is not None for row in funded
        ),
        "average_processing_days": _average(processing_days),
        "average_disbursement_days": _average(disbursement_days),
        "delay_sample_size": len(processing_days),
        "disbursement_delay_sample_size": len(disbursement_days),
        "financing_rate": round(100.0 * len(funded) / total, 2) if total else None,
        "rejection_rate": round(100.0 * len(rejected) / total, 2) if total else None,
        "reconciliation_rate": round(100.0 * len(matched) / total, 2) if total else None,
    }


def pipeline(filters: AnalyticsFilters) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        key = (
            str(row.get("status__pipeline_stage") or "intake"),
            str(row.get("status__code") or "unmapped"),
            str(row.get("status__label") or "Unmapped status"),
        )
        grouped[key].append(row)
    stage_order = {
        "intake": 1,
        "waiting_visit": 2,
        "waiting_decision": 3,
        "waiting_disbursement": 4,
        "completed": 5,
    }
    results = []
    for (stage, code, label), rows in grouped.items():
        registered = [row for row in rows if _is_registered(row)]
        results.append(
            {
                "pipeline_stage": stage,
                "status_code": code,
                "status_label": label,
                "observed_records": len(rows),
                "total_requests": len(registered),
                "funded_requests": sum(_is_funded_request(row) for row in rows),
                "rejected_requests": sum(_is_rejected_request(row) for row in rows),
                "tb2_only_observations": sum(0 for row in rows),
                "requested_amount": _sum_amount(registered, "requested_amount"),
                "provisional": any(_row_is_provisional(row) for row in rows),
            }
        )
    return sorted(
        results,
        key=lambda row: (stage_order.get(str(row["pipeline_stage"]), 6), str(row["status_label"])),
    )


def agency_comparison(filters: AnalyticsFilters) -> list[dict[str, object]]:
    catalog = _agency_catalog(filters)
    active_gp_counts: dict[str, int] = defaultdict(int)
    for source_agency_id in GPDimension.objects.filter(is_active=True).values_list(
        "agency_id", flat=True
    ):
        active_gp_counts[str(source_agency_id)] += 1
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        grouped[str(row["agency_id"])].append(row)
    coverage = _coverage_by_agency(filters)
    results: list[dict[str, object]] = []
    for agency_id, agency in catalog.items():
        rows = grouped.get(agency_id, [])
        registered = [row for row in rows if _is_registered(row)]
        funded = [row for row in rows if _is_funded_request(row)]
        rejected = [row for row in rows if _is_rejected_request(row)]
        matched = [row for row in rows if _is_matched_request(row)]
        processing = _processing_durations(registered)
        disbursement = _disbursement_durations(funded)
        total = len(registered)
        gp_assigned = [row for row in registered if row.get("gp_id")]
        active_gp_count = active_gp_counts.get(agency_id, 0)
        gp_dates = [
            row["request_date__calendar_date"]
            for row in gp_assigned
            if isinstance(row.get("request_date__calendar_date"), date)
        ]
        source_coverage = _source_coverage(rows)
        coverage_row = coverage.get(agency_id, {})
        provisional = any(_row_is_provisional(row) for row in rows) or not bool(
            coverage_row.get("ranking_eligible")
        )
        result: dict[str, object] = {
            "agency_id": agency_id,
            "agency_code": agency["name"],
            "agency_name": agency["name"],
            "observed_records": len(rows) if rows else None,
            "total_requests": total if rows else None,
            "funded_requests": len(funded) if rows else None,
            "nonfunded_requests": total - len(funded) if rows else None,
            "rejected_requests": len(rejected) if rows else None,
            "open_or_unknown_requests": sum(
                not _is_funded_request(row) and not _is_rejected_request(row) for row in registered
            )
            if rows
            else None,
            "active_requests": sum(bool(row.get("is_open")) for row in registered)
            if rows
            else None,
            "matched_requests": len(matched) if rows else None,
            "portfolio_observations": len(rows) if rows else None,
            "requested_amount": _sum_amount(registered, "requested_amount") if rows else None,
            "disbursed_amount": _sum_amount(funded, "disbursed_amount") if rows else None,
            "disbursed_amount_sample_size": sum(
                row.get("disbursed_amount") is not None for row in funded
            )
            if rows
            else None,
            "average_processing_days": _average(processing),
            "processing_duration_days_sum": sum(processing),
            "delay_sample_size": len(processing),
            "average_disbursement_days": _average(disbursement),
            "disbursement_duration_days_sum": sum(disbursement),
            "disbursement_delay_sample_size": len(disbursement),
            "invalid_delay_count": sum(_has_date_anomaly(row) for row in registered),
            "date_anomaly_count": sum(_has_date_anomaly(row) for row in registered),
            "financing_rate": round(100.0 * len(funded) / total, 2) if total else None,
            "rejection_rate": round(100.0 * len(rejected) / total, 2) if total else None,
            "reconciliation_rate": round(100.0 * len(matched) / total, 2) if total else None,
            "active_gp_count": active_gp_count,
            "gp_assigned_requests": len(gp_assigned) if rows else None,
            "gp_unassigned_requests": total - len(gp_assigned) if rows else None,
            "gp_coverage_rate": round(100.0 * len(gp_assigned) / total, 2) if total else None,
            "requests_per_active_gp": round(total / active_gp_count, 2)
            if active_gp_count and rows
            else None,
            "last_gp_activity_date": max(gp_dates).isoformat() if gp_dates else None,
            "source_coverage": source_coverage,
            "provisional": provisional,
            "data_status": "no_observed_data"
            if not rows
            else "tb2_only_observation"
            if source_coverage == "tb2_only"
            else "observed_data",
            **coverage_row,
        }
        result["limitations"] = _agency_limitations(result)
        results.append(result)
    results.sort(
        key=lambda row: (
            not bool(row.get("ranking_eligible")),
            -_as_int(row.get("total_requests")),
            str(row["agency_name"]),
        )
    )
    return results


def _source_coverage(rows: Sequence[Mapping[str, Any]]) -> str:
    has_tb1 = bool(rows)
    has_tb2 = bool(rows)
    return (
        "both"
        if has_tb1 and has_tb2
        else "tb1_only"
        if has_tb1
        else "tb2_only"
        if has_tb2
        else "none"
    )


def _agency_limitations(row: Mapping[str, Any]) -> list[dict[str, str]]:
    limitations = []
    if row.get("missing_tb1_months"):
        limitations.append(
            {
                "code": "missing_tb1_agency_months",
                "message": "Expected TB1 months are missing; demand ranking is disabled.",
            }
        )
    if row.get("tb1_unusable_submitted_months"):
        limitations.append(
            {
                "code": "unusable_tb1_agency_months",
                "message": "Partial or quarantined TB1 months make this agency provisional.",
            }
        )
    return limitations


def _processing_durations(rows: Iterable[Mapping[str, Any]]) -> list[int]:
    return [
        duration
        for row in rows
        if _is_terminal_request(row)
        and (duration := _valid_days(row.get("request_date__calendar_date"), _outcome_date(row)))
        is not None
    ]


def _disbursement_durations(rows: Iterable[Mapping[str, Any]]) -> list[int]:
    return [
        duration
        for row in rows
        if (
            duration := _valid_days(
                row.get("request_date__calendar_date"), row.get("disbursement_date__calendar_date")
            )
        )
        is not None
    ]


def _role_delay_definition(role: str) -> tuple[str, str, str]:
    if role == "gp":
        return (
            "Affectation GP → visite",
            "gp_assignment_date__calendar_date",
            "visit_date__calendar_date",
        )
    return (
        "Demande → réception agence",
        "request_date__calendar_date",
        "reception_date__calendar_date",
    )


def employee_comparison(
    filters: AnalyticsFilters, *, role: str | None
) -> tuple[list[dict[str, object]], int]:
    requested_role = "ca_caa" if role == "ca" else role
    role_specs = [("gp", "gp_id", "gp__name"), ("ca_caa", "ca_caa_id", "ca_caa__name")]
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        for employee_role, id_field, name_field in role_specs:
            if requested_role and requested_role != employee_role:
                continue
            employee_id = row.get(id_field)
            if employee_id is not None:
                grouped[(str(row["agency_id"]), employee_role, str(employee_id))].append(
                    row | {"_employee_name": row.get(name_field)}
                )
    results: list[dict[str, object]] = []
    for (agency_id, employee_role, employee_id), rows in grouped.items():
        registered = [row for row in rows if _is_registered(row)]
        funded = [row for row in rows if _is_funded_request(row)]
        processing = _processing_durations(registered)
        disbursement = _disbursement_durations(funded)
        role_label, role_start, role_end = _role_delay_definition(employee_role)
        role_delays = [
            duration
            for row in registered
            if (duration := _valid_days(row.get(role_start), row.get(role_end))) is not None
        ]
        reveal_name = not filters.mask_employee_names and (
            filters.employee_id is None
            or (filters.employee_role == employee_role and str(filters.employee_id) == employee_id)
        )
        name = (
            str(rows[0].get("_employee_name") or "Employee")
            if reveal_name
            else f"Employee {employee_id[:8]}"
        )
        total = len(registered)
        results.append(
            {
                "agency_id": agency_id,
                "agency_code": rows[0]["agency__name"],
                "agency_name": rows[0]["agency__name"],
                "employee_role": "ca" if employee_role == "ca_caa" else employee_role,
                "employee_name": name,
                "identity_status": "governed" if reveal_name else "masked_governed",
                "observed_records": len(rows),
                "total_requests": total,
                "funded_requests": len(funded),
                "rejected_requests": sum(_is_rejected_request(row) for row in rows),
                "active_requests": sum(bool(row.get("is_open")) for row in registered),
                "average_processing_days": _average(processing),
                "processing_duration_days_sum": sum(processing),
                "delay_sample_size": len(processing),
                "average_disbursement_days": _average(disbursement),
                "disbursement_duration_days_sum": sum(disbursement),
                "disbursement_delay_sample_size": len(disbursement),
                "role_delay_label": role_label,
                "average_role_delay_days": _average(role_delays),
                "role_delay_duration_days_sum": sum(role_delays),
                "role_delay_sample_size": len(role_delays),
                "financing_rate": round(100.0 * len(funded) / total, 2) if total else None,
                "source_coverage": _source_coverage(rows),
                "provisional": any(_row_is_provisional(row) for row in rows),
            }
        )
    return _suppress_low_frequency_employees(results)


def _suppress_low_frequency_employees(
    rows: list[dict[str, object]], *, minimum_count: int = 1
) -> tuple[list[dict[str, object]], int]:
    """Keep governed operational assignments visible, even in a small new dataset.

    Employee identities are reference-data records and the endpoint requires an authenticated
    operations user.  Hiding groups below five records made the CA/GP workload and delay views
    appear empty until an agency accumulated enough history.
    """
    visible = [row for row in rows if _as_int(row.get("total_requests")) >= minimum_count]
    suppressed_count = len(rows) - len(visible)
    for row in visible:
        _suppress_employee_samples(row, minimum_count)
    visible.sort(key=lambda row: (-_as_int(row.get("total_requests")), str(row["employee_name"])))
    return visible, suppressed_count


def _suppress_employee_samples(row: dict[str, object], minimum_count: int) -> None:
    for sample, average, total in (
        ("delay_sample_size", "average_processing_days", "processing_duration_days_sum"),
        (
            "disbursement_delay_sample_size",
            "average_disbursement_days",
            "disbursement_duration_days_sum",
        ),
        ("role_delay_sample_size", "average_role_delay_days", "role_delay_duration_days_sum"),
    ):
        if _as_int(row.get(sample)) < minimum_count:
            row[average] = None
            row[total] = None


INTERVALS = (
    (
        "request_to_reception",
        "Demande → réception agence",
        "request_date__calendar_date",
        "reception_date__calendar_date",
        "all",
    ),
    (
        "reception_to_assignment",
        "Réception agence → affectation GP",
        "reception_date__calendar_date",
        "gp_assignment_date__calendar_date",
        "all",
    ),
    (
        "assignment_to_visit",
        "Affectation GP → visite",
        "gp_assignment_date__calendar_date",
        "visit_date__calendar_date",
        "all",
    ),
    (
        "visit_to_outcome",
        "Visite → résultat",
        "visit_date__calendar_date",
        "_outcome",
        "terminal",
    ),
    (
        "request_to_outcome",
        "Demande → résultat",
        "request_date__calendar_date",
        "_outcome",
        "terminal",
    ),
    (
        "request_to_disbursement",
        "Demande → décaissement",
        "request_date__calendar_date",
        "disbursement_date__calendar_date",
        "funded",
    ),
    (
        "request_to_rejection",
        "Demande → rejet",
        "request_date__calendar_date",
        "rejection_date__calendar_date",
        "rejected",
    ),
)


def delays(
    filters: AnalyticsFilters, *, interval: str | None
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    registered = [row for row in _fact_rows(filters) if _is_registered(row)]
    interval_rows = []
    for code, label, start_field, end_field, eligibility in INTERVALS:
        if interval and interval != code:
            continue
        eligible = [
            row
            for row in registered
            if eligibility == "all"
            or (eligibility == "funded" and _is_funded_request(row))
            or (eligibility == "rejected" and _is_rejected_request(row))
            or (eligibility == "terminal" and _is_terminal_request(row))
        ]
        statuses = [
            _duration_status(
                row.get(start_field),
                _outcome_date(row) if end_field == "_outcome" else row.get(end_field),
            )
            for row in eligible
        ]
        values = [item[1] for item in statuses if item[0] == "complete" and item[1] is not None]
        interval_rows.append(
            {
                "interval_code": code,
                "interval_label": label,
                "eligible_requests": len(eligible),
                "sample_size": len(values),
                "missing_start_count": sum(item[0] == "missing_start" for item in statuses),
                "missing_end_count": sum(item[0] == "missing_end" for item in statuses),
                "invalid_order_count": sum(item[0] == "invalid_order" for item in statuses),
                "outlier_count": sum(item[0] == "outlier" for item in statuses),
                "future_date_count": sum(item[0] == "future_date" for item in statuses),
                "average_days": _average(int(value) for value in values),
                "minimum_days": min(values) if values else None,
                "maximum_days": max(values) if values else None,
            }
        )
    return interval_rows, _aging_rows(registered)


def _duration_status(start: Any, end: Any) -> tuple[str, int | None]:
    if not isinstance(start, date):
        return "missing_start", None
    if not isinstance(end, date):
        return "missing_end", None
    if start > timezone.localdate() or end > timezone.localdate():
        return "future_date", None
    if end < start:
        return "invalid_order", None
    duration = (end - start).days
    return ("outlier", None) if duration > 365 else ("complete", duration)


def _aging_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str], list[tuple[Mapping[str, Any], int | None]]] = (
        defaultdict(list)
    )
    today = timezone.localdate()
    for row in rows:
        if not row.get("is_open"):
            continue
        stage = str(row.get("status__pipeline_stage") or "unknown")
        anchor = _stage_anchor(row, stage)
        days = (today - anchor).days if isinstance(anchor, date) and anchor <= today else None
        bucket = (
            "Unknown"
            if days is None
            else "0-3 days"
            if days <= 3
            else "4-7 days"
            if days <= 7
            else "8-14 days"
            if days <= 14
            else "15-30 days"
            if days <= 30
            else "31+ days"
        )
        key = (
            stage,
            str(row.get("status__code") or "unmapped"),
            str(row.get("status__label") or "Unmapped status"),
            bucket,
        )
        groups[key].append((row, days))
    result = []
    for (stage, code, label, bucket), items in groups.items():
        aging_days = [value for _, value in items if value is not None]
        result.append(
            {
                "pipeline_stage": stage,
                "status_code": code,
                "status_label": label,
                "aging_bucket": bucket,
                "application_count": len(items),
                "missing_anchor_count": sum(value is None for _, value in items),
                "average_stage_aging_days": _average(aging_days),
                "maximum_stage_aging_days": max(aging_days) if aging_days else None,
                "requested_amount": _sum_amount((row for row, _ in items), "requested_amount"),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            str(row["pipeline_stage"]),
            str(row["aging_bucket"]),
            str(row["status_label"]),
        ),
    )


def _stage_anchor(row: Mapping[str, Any], stage: str) -> date | None:
    required_fields: dict[str, str] = {
        StatusDimension.PipelineStage.INTAKE: "request_date__calendar_date",
        StatusDimension.PipelineStage.WAITING_VISIT: "gp_assignment_date__calendar_date",
        StatusDimension.PipelineStage.WAITING_DECISION: "visit_date__calendar_date",
        StatusDimension.PipelineStage.WAITING_DISBURSEMENT: "visit_date__calendar_date",
    }
    required_field = required_fields.get(stage)
    anchor = row.get(required_field) if required_field is not None else None
    return anchor if isinstance(anchor, date) else None


def rejections(filters: AnalyticsFilters) -> tuple[list[dict[str, object]], int]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        if not row.get("is_rejected") or not row.get("rejection_reason__name"):
            continue
        key = (
            str(row["agency_id"]),
            str(row.get("gp_id") or ""),
            str(row.get("gp__name") or "Non affecté"),
            str(row["rejection_reason__name"]),
        )
        grouped[key].append(row)
    results = []
    for (agency_id, gp_id, gp_name, label), rows in grouped.items():
        results.append(
            {
                "agency_id": agency_id,
                "agency_code": rows[0]["agency__name"],
                "agency_name": rows[0]["agency__name"],
                "gp_id": gp_id or None,
                "gp_name": gp_name,
                "reason_code": label,
                "reason_label": label,
                "reason_category": "",
                "rejected_requests": sum(_is_rejected_request(row) for row in rows),
                "observed_rejections": len(rows),
                "tb2_only_rejections": sum(not _is_registered(row) for row in rows),
                "rejected_amount": _sum_amount(
                    (row for row in rows if _is_rejected_request(row)), "requested_amount"
                ),
                "agency_count": 1,
                "provisional": any(_row_is_provisional(row) for row in rows),
            }
        )
    results.sort(key=lambda row: (-_as_int(row.get("rejected_requests")), str(row["reason_label"])))
    return results, 0


def activities(filters: AnalyticsFilters) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        if not row.get("activity__name"):
            continue
        key = (
            str(row["agency_id"]),
            str(row["activity__name"]),
        )
        grouped[key].append(row)
    results = []
    for (agency_id, label), rows in grouped.items():
        registered = [row for row in rows if _is_registered(row)]
        funded = [row for row in rows if _is_funded_request(row)]
        results.append(
            {
                "agency_id": agency_id,
                "agency_code": rows[0]["agency__name"],
                "agency_name": rows[0]["agency__name"],
                "activity_label": label,
                "activity_source": "controlled",
                "observed_records": len(rows),
                "total_requests": len(registered),
                "funded_requests": len(funded),
                "rejected_requests": sum(_is_rejected_request(row) for row in rows),
                "requested_amount": _sum_amount(registered, "requested_amount"),
                "agency_count": 1,
                "financing_rate": round(100.0 * len(funded) / len(registered), 2)
                if registered
                else None,
                "provisional": any(_row_is_provisional(row) for row in rows),
            }
        )
    return sorted(
        results,
        key=lambda row: (
            -_as_int(row["total_requests"]),
            str(row["agency_name"]),
            str(row["activity_label"]),
        ),
    )


def products_and_requests(filters: AnalyticsFilters) -> list[dict[str, object]]:
    """Aggregate governed request and credit classifications at an agency-month grain."""

    grouped: dict[tuple[str, date, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _fact_rows(filters):
        request_date = row.get("request_date__calendar_date")
        request_type = row.get("request_type__name")
        credit_type = row.get("credit_type__name")
        if (
            not isinstance(request_date, date)
            or not isinstance(request_type, str)
            or not request_type
            or not isinstance(credit_type, str)
            or not credit_type
        ):
            continue
        key = (
            str(row["agency_id"]),
            request_date.replace(day=1),
            request_type,
            credit_type,
        )
        grouped[key].append(row)

    results = []
    for (agency_id, month, request_type, credit_type), rows in grouped.items():
        results.append(
            {
                "agency_id": agency_id,
                "agency_name": rows[0]["agency__name"],
                "month": month.isoformat(),
                "request_type_label": request_type,
                "credit_type_label": credit_type,
                "total_requests": len(rows),
                "requested_amount": _sum_amount(rows, "requested_amount"),
                "funded_requests": sum(_is_funded_request(row) for row in rows),
                "rejected_requests": sum(_is_rejected_request(row) for row in rows),
                "active_requests": sum(bool(row.get("is_open")) for row in rows),
            }
        )
    return sorted(
        results,
        key=lambda row: (
            str(row["month"]),
            str(row["request_type_label"]),
            str(row["credit_type_label"]),
            str(row["agency_name"]),
        ),
    )


def response_payload(
    filters: AnalyticsFilters,
    *,
    results: object | None = None,
    summary: object | None = None,
    extra_limitations: Sequence[dict[str, str]] = (),
) -> dict[str, object]:
    completeness_payload = completeness(filters)
    if extra_limitations:
        existing = completeness_payload.get("limitations")
        limitations = list(existing) if isinstance(existing, list) else []
        limitations.extend(extra_limitations)
        completeness_payload["limitations"] = limitations
        completeness_payload["provisional"] = True
    payload: dict[str, object] = {
        "filters": filters.as_payload(),
        "completeness": completeness_payload,
    }
    if results is not None:
        payload["results"] = results
    if summary is not None:
        payload["summary"] = summary
    return payload
