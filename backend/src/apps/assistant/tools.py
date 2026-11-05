from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import Count, Min
from django.utils import timezone

from apps.alerts.models import DelayAlert
from apps.analytics import services as analytics
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import ImportBatch
from apps.warehouse.models import AgencyDimension, FactCreditRequest


class ToolInputError(ValueError):
    """Raised when model-selected tool arguments do not satisfy domain constraints."""


@dataclass(slots=True)
class ToolResult:
    data: dict[str, object]
    sources: list[dict[str, str]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)


DATE_FILTER_PROPERTIES: dict[str, object] = {
    "date_from": {
        "type": ["string", "null"],
        "description": "First month of the reporting period as YYYY-MM-DD, or null.",
    },
    "date_to": {
        "type": ["string", "null"],
        "description": "Last month of the reporting period as YYYY-MM-DD, or null.",
    },
    "agency_names": {
        "type": ["array", "null"],
        "items": {"type": "string"},
        "description": "Exact agency names requested by the user, or null for all agencies.",
    },
}


def _analytics_tool(*, name: str, description: str) -> dict[str, object]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": dict(DATE_FILTER_PROPERTIES),
            "required": list(DATE_FILTER_PROPERTIES),
            "additionalProperties": False,
        },
        "strict": True,
    }


TOOL_DEFINITIONS: list[dict[str, object]] = [
    _analytics_tool(
        name="get_portfolio_summary",
        description=(
            "Return governed portfolio totals, amounts, rates, and average processing delays. "
            "Use for overview, volume, amount, financing, rejection, or reconciliation questions."
        ),
    ),
    _analytics_tool(
        name="compare_agencies",
        description=(
            "Compare governed request, funding, rejection, workload, and delay metrics by agency."
        ),
    ),
    _analytics_tool(
        name="get_delay_breakdown",
        description=(
            "Return lifecycle interval statistics, open-request aging, and current delay-alert "
            "counts. Use for delay, blockage, aging, or overdue questions."
        ),
    ),
    _analytics_tool(
        name="get_rejection_breakdown",
        description="Return rejection counts and amounts grouped by agency and governed reason.",
    ),
    {
        "type": "function",
        "name": "get_request_timeline",
        "description": (
            "Look up one published credit-request lifecycle by its exact governed reference. "
            "Never infer a reference."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference": {"type": "string"},
                "agency_name": {"type": ["string", "null"]},
            },
            "required": ["reference", "agency_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_import_summary",
        "description": (
            "Return sanitized status, row counts, and grouped correction issues for an import "
            "batch. Pass null to inspect the latest batch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": ["string", "null"],
                    "description": "Import batch UUID, or null for the latest batch.",
                }
            },
            "required": ["batch_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _optional_date(arguments: Mapping[str, object], key: str) -> date | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ToolInputError(f"{key} must be an ISO date.")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ToolInputError(f"{key} must use YYYY-MM-DD.") from exc


def _resolve_agencies(raw_names: object) -> tuple[UUID, ...]:
    if raw_names is None:
        return ()
    if not isinstance(raw_names, list) or len(raw_names) > 10:
        raise ToolInputError("agency_names must be a list of at most ten names.")
    resolved: list[UUID] = []
    missing: list[str] = []
    for raw_name in raw_names:
        if not isinstance(raw_name, str) or not raw_name.strip() or len(raw_name) > 120:
            raise ToolInputError("Every agency name must be non-empty text.")
        name = raw_name.strip()
        exact = AgencyDimension.objects.filter(name__iexact=name).first()
        if exact is None:
            candidates = list(AgencyDimension.objects.filter(name__icontains=name)[:2])
            exact = candidates[0] if len(candidates) == 1 else None
        if exact is None:
            missing.append(name)
        elif exact.pk not in resolved:
            resolved.append(exact.pk)
    if missing:
        raise ToolInputError(f"Unknown or ambiguous agencies: {', '.join(missing)}.")
    return tuple(resolved)


def _filters(arguments: Mapping[str, object], *, user: Any) -> analytics.AnalyticsFilters:
    current_month = _month_start(timezone.localdate())
    date_to = _month_start(_optional_date(arguments, "date_to") or current_month)
    date_from = _month_start(_optional_date(arguments, "date_from") or _add_months(date_to, -11))
    if date_from > date_to:
        raise ToolInputError("date_from cannot be later than date_to.")
    months = (date_to.year - date_from.year) * 12 + date_to.month - date_from.month + 1
    if months > 36:
        raise ToolInputError("The assistant can query at most 36 months at a time.")
    agency_ids = _resolve_agencies(arguments.get("agency_names"))
    return analytics.AnalyticsFilters.from_validated(
        {"date_from": date_from, "date_to": date_to, "agency": agency_ids},
        user=user,
    )


def _analytics_source(filters: analytics.AnalyticsFilters, label: str) -> dict[str, str]:
    return {
        "type": "analytics",
        "label": label,
        "detail": f"{filters.date_from.isoformat()} - {filters.date_to.isoformat()}",
    }


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, bool | int | float | Decimal | str) else 0


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, bool | int | float | Decimal | str) else 0.0


def _portfolio(arguments: Mapping[str, object], user: Any) -> ToolResult:
    filters = _filters(arguments, user=user)
    payload = analytics.response_payload(filters, summary=analytics.overview(filters))
    return ToolResult(
        data=payload,
        sources=[_analytics_source(filters, "Vue d'ensemble du portefeuille")],
        links=[{"label": "Ouvrir la vue d'ensemble", "url": "/"}],
    )


def _agencies(arguments: Mapping[str, object], user: Any) -> ToolResult:
    filters = _filters(arguments, user=user)
    results = analytics.agency_comparison(filters)
    return ToolResult(
        data={
            "filters": filters.as_payload(),
            "results": results[:25],
            "result_count": len(results),
            "completeness": analytics.completeness(filters),
        },
        sources=[_analytics_source(filters, "Comparaison des agences")],
        links=[{"label": "Ouvrir la comparaison réseau", "url": "/agencies"}],
    )


def _delays(arguments: Mapping[str, object], user: Any) -> ToolResult:
    filters = _filters(arguments, user=user)
    interval_rows, aging_rows = analytics.delays(filters, interval=None)
    alerts = DelayAlert.objects.filter(
        reporting_period__gte=filters.date_from,
        reporting_period__lt=_add_months(filters.date_to, 1),
    )
    if filters.agency_ids:
        alerts = alerts.filter(agency_id__in=filters.agency_ids)
    alert_groups = list(
        alerts.values("agency__name", "rule", "state")
        .annotate(count=Count("id"), oldest_started_on=Min("started_on"))
        .order_by("agency__name", "rule", "state")[:50]
    )
    return ToolResult(
        data={
            "filters": filters.as_payload(),
            "intervals": interval_rows,
            "aging": aging_rows[:50],
            "current_alerts": alert_groups,
            "completeness": analytics.completeness(filters),
        },
        sources=[_analytics_source(filters, "Délais et alertes")],
        links=[
            {"label": "Ouvrir les délais", "url": "/delays"},
            {"label": "Ouvrir les alertes", "url": "/alerts"},
        ],
    )


def _rejections(arguments: Mapping[str, object], user: Any) -> ToolResult:
    filters = _filters(arguments, user=user)
    rows, suppressed_groups = analytics.rejections(filters)
    grouped: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"rejected_requests": 0, "rejected_amount": 0.0}
    )
    for row in rows:
        key = (str(row["agency_name"]), str(row["reason_label"]))
        item = grouped[key]
        item["agency_name"], item["reason_label"] = key
        item["rejected_requests"] = _as_int(item["rejected_requests"]) + _as_int(
            row.get("rejected_requests")
        )
        item["rejected_amount"] = _as_float(item["rejected_amount"]) + _as_float(
            row.get("rejected_amount")
        )
    results = sorted(
        grouped.values(),
        key=lambda row: (-_as_int(row["rejected_requests"]), str(row["reason_label"])),
    )
    return ToolResult(
        data={
            "filters": filters.as_payload(),
            "results": results[:50],
            "suppressed_groups": suppressed_groups,
            "completeness": analytics.completeness(filters),
        },
        sources=[_analytics_source(filters, "Analyse des rejets")],
        links=[{"label": "Ouvrir l'analyse des rejets", "url": "/rejections"}],
    )


def _request_timeline(arguments: Mapping[str, object], _user: Any) -> ToolResult:
    reference = arguments.get("reference")
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 32:
        raise ToolInputError("A dossier reference is required.")
    queryset = FactCreditRequest.objects.filter(
        reference__iexact=reference.strip(),
        current_tb1_row__isnull=False,
        current_tb2_row__isnull=False,
    ).select_related(
        "agency",
        "status",
        "request_date",
        "reception_date",
        "gp_assignment_date",
        "visit_date",
        "disbursement_date",
        "rejection_date",
        "rejection_reason",
    )
    agency_name = arguments.get("agency_name")
    if agency_name is not None:
        if not isinstance(agency_name, str) or not agency_name.strip() or len(agency_name) > 120:
            raise ToolInputError("agency_name must be non-empty text or null.")
        queryset = queryset.filter(agency__name__iexact=agency_name.strip())
    matches = list(queryset[:6])
    if not matches:
        return ToolResult(
            data={"found": False, "reference": reference.strip()},
            sources=[{"type": "dossier", "label": "Entrepôt des dossiers publiés"}],
        )
    if len(matches) > 1:
        return ToolResult(
            data={
                "found": True,
                "ambiguous": True,
                "candidates": [
                    {
                        "agency_name": item.agency.name,
                        "status": item.status.name if item.status else None,
                    }
                    for item in matches
                ],
            },
            sources=[{"type": "dossier", "label": "Entrepôt des dossiers publiés"}],
        )
    item = matches[0]

    def calendar_value(attribute: str) -> str | None:
        dimension = getattr(item, attribute)
        return dimension.calendar_date.isoformat() if dimension is not None else None

    return ToolResult(
        data={
            "found": True,
            "ambiguous": False,
            "id": str(item.pk),
            "reference": item.reference,
            "agency_name": item.agency.name,
            "status": item.status.name if item.status else None,
            "pipeline_stage": item.status.pipeline_stage if item.status else None,
            "rejection_reason": item.rejection_reason.name if item.rejection_reason else None,
            "missing_from_latest_tb2_period": item.missing_from_latest_tb2_period,
            "timeline": {
                "request": calendar_value("request_date"),
                "reception": calendar_value("reception_date"),
                "gp_assignment": calendar_value("gp_assignment_date"),
                "visit": calendar_value("visit_date"),
                "disbursement": calendar_value("disbursement_date"),
                "rejection": calendar_value("rejection_date"),
            },
        },
        sources=[{"type": "dossier", "label": f"Dossier {item.reference}"}],
        links=[{"label": "Ouvrir le dossier", "url": f"/applications/{item.pk}"}],
    )


def _import_summary(arguments: Mapping[str, object], _user: Any) -> ToolResult:
    batch_id = arguments.get("batch_id")
    batches = ImportBatch.objects.select_related("detected_agency")
    if batch_id is None:
        batch = batches.order_by("-created_at").first()
    else:
        if not isinstance(batch_id, str):
            raise ToolInputError("batch_id must be a UUID or null.")
        try:
            parsed_id = UUID(batch_id)
        except ValueError as exc:
            raise ToolInputError("batch_id must be a valid UUID.") from exc
        batch = batches.filter(pk=parsed_id).first()
    if batch is None:
        return ToolResult(
            data={"found": False},
            sources=[{"type": "import", "label": "Historique des imports"}],
        )
    issues = list(
        DataQualityIssue.objects.filter(batch=batch)
        .values("severity", "code", "field_name", "message")
        .annotate(count=Count("id"))
        .order_by("-count", "code")[:20]
    )
    return ToolResult(
        data={
            "found": True,
            "batch": {
                "id": str(batch.pk),
                "workbook_type": batch.workbook_type,
                "status": batch.status,
                "agency_name": batch.detected_agency.name if batch.detected_agency else None,
                "reporting_period": batch.reporting_period,
                "rows_discovered": batch.rows_discovered,
                "rows_imported": batch.rows_imported,
                "rows_rejected": batch.rows_rejected,
                "sanitized_error": batch.error_message,
                "created_at": batch.created_at,
            },
            "grouped_issues": issues,
        },
        sources=[{"type": "import", "label": f"Rapport d'import {batch.pk}"}],
        links=[{"label": "Ouvrir le rapport d'import", "url": f"/imports/{batch.pk}"}],
    )


TOOL_HANDLERS: dict[str, Callable[[Mapping[str, object], Any], ToolResult]] = {
    "get_portfolio_summary": _portfolio,
    "compare_agencies": _agencies,
    "get_delay_breakdown": _delays,
    "get_rejection_breakdown": _rejections,
    "get_request_timeline": _request_timeline,
    "get_import_summary": _import_summary,
}


def execute_tool(name: str, arguments: Mapping[str, object], *, user: Any) -> ToolResult:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ToolInputError(f"Unsupported assistant tool: {name}.")
    return handler(arguments, user)
