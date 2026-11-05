from __future__ import annotations

import calendar
import hashlib
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import User
from apps.alerts.models import DelayAlert
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import (
    ImportBatch,
    MatchStatus,
    TB1RequestStagingRow,
    TB2SnapshotStagingRow,
    ValidationStatus,
)
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditRequestStatusHistory,
    CreditTypeDimension,
    DateDimension,
    FactCreditRequest,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    StatusDimension,
)
from apps.warehouse.services import ensure_status_dimensions

SHOWCASE_NAMESPACE = uuid.UUID("bd6f54db-ef0d-4d4d-8a29-1f9d7517b465")
DEFAULT_MONTHS = 12
DEFAULT_REQUESTS_PER_MONTH = 5

CA_NAMES = (
    "Amira Ben Salah",
    "Youssef Trabelsi",
    "Ines Gharbi",
    "Mohamed Ayari",
    "Sarra Jlassi",
    "Walid Hamdi",
)
GP_NAMES = (
    "Nadia Mansouri",
    "Karim Bouazizi",
    "Rim Khelifi",
    "Sami Chaabane",
    "Leila Mejri",
    "Ahmed Ferjani",
)


class Command(BaseCommand):
    help = "Populate the local database directly with a reusable showcase dataset."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--months", type=int, default=DEFAULT_MONTHS)
        parser.add_argument(
            "--requests-per-month",
            type=int,
            default=DEFAULT_REQUESTS_PER_MONTH,
        )

    def handle(self, *_args: Any, **options: Any) -> None:
        month_count = int(options["months"])
        requests_per_month = int(options["requests_per_month"])
        if not 1 <= month_count <= 24:
            self.stderr.write(self.style.ERROR("--months must be between 1 and 24."))
            return
        if not 1 <= requests_per_month <= 20:
            self.stderr.write(self.style.ERROR("--requests-per-month must be between 1 and 20."))
            return

        call_command("seed_operational_reference_data", verbosity=0)
        with transaction.atomic():
            summary = self._seed(month_count, requests_per_month)

        self.stdout.write(
            self.style.SUCCESS(
                "Showcase data ready: "
                f"{summary['agencies']} agencies, {summary['months']} months, "
                f"{summary['facts']} demo dossiers, {summary['batches']} imports, "
                f"and {summary['alerts']} delay alerts."
            )
        )

    def _seed(self, month_count: int, requests_per_month: int) -> dict[str, int]:
        today = timezone.localdate()
        months = [
            _add_months(today.replace(day=1), offset) for offset in range(-(month_count - 1), 1)
        ]
        agencies = list(
            AgencyDimension.objects.filter(is_active=True, code__isnull=False).order_by("name")
        )
        statuses = ensure_status_dimensions()
        credit_types = list(CreditTypeDimension.objects.filter(is_active=True).order_by("name"))
        activities = list(ActivityDimension.objects.filter(is_active=True).order_by("name"))
        request_types = list(RequestTypeDimension.objects.filter(is_active=True).order_by("name"))
        rejection_reasons = list(
            RejectionReasonDimension.objects.filter(is_active=True).order_by("name")
        )
        uploader = User.objects.filter(is_active=True).order_by("username").first()

        facts: list[FactCreditRequest] = []
        batches: set[uuid.UUID] = set()
        for agency_index, agency in enumerate(agencies):
            ca_staff = self._staff_for_agency(CADimension, agency, agency_index, CA_NAMES)
            gp_staff = self._staff_for_agency(GPDimension, agency, agency_index, GP_NAMES)
            for month_index, reporting_period in enumerate(months):
                is_partial = (agency_index * 3 + month_index) % 19 == 0
                tb1_batch = self._batch(
                    agency=agency,
                    reporting_period=reporting_period,
                    workbook_type=ImportBatch.WorkbookType.TB1,
                    uploader=uploader,
                    partial=is_partial,
                    today=today,
                )
                tb2_batch = self._batch(
                    agency=agency,
                    reporting_period=reporting_period,
                    workbook_type=ImportBatch.WorkbookType.TB2,
                    uploader=uploader,
                    partial=False,
                    today=today,
                )
                batches.update((tb1_batch.pk, tb2_batch.pk))

                for request_index in range(requests_per_month):
                    fact = self._request(
                        agency=agency,
                        agency_index=agency_index,
                        reporting_period=reporting_period,
                        month_index=month_index,
                        request_index=request_index,
                        requests_per_month=requests_per_month,
                        tb1_batch=tb1_batch,
                        tb2_batch=tb2_batch,
                        ca_staff=ca_staff,
                        gp_staff=gp_staff,
                        credit_types=credit_types,
                        activities=activities,
                        request_types=request_types,
                        rejection_reasons=rejection_reasons,
                        statuses=statuses,
                        current_period=months[-1],
                    )
                    facts.append(fact)

                if is_partial:
                    self._invalid_demo_row(tb1_batch, agency, reporting_period)

        self._synchronize_batch_counts(batches)
        alert_count = self._seed_alerts(facts, today.replace(day=1))
        return {
            "agencies": len(agencies),
            "months": len(months),
            "facts": len(facts),
            "batches": len(batches),
            "alerts": alert_count,
        }

    def _staff_for_agency(
        self,
        model: type[CADimension] | type[GPDimension],
        agency: AgencyDimension,
        agency_index: int,
        names: tuple[str, ...],
    ) -> tuple[CADimension | GPDimension, CADimension | GPDimension]:
        selected: list[CADimension | GPDimension] = []
        existing: list[Any] = list(model.objects.filter(agency=agency))
        for offset in range(2):
            name = names[(agency_index * 2 + offset) % len(names)]
            employee = next((item for item in existing if str(item.name) == name), None)
            if employee is None:
                employee = model.objects.create(
                    agency=agency,
                    name=name,
                    email=(
                        f"demo.{agency.code}.{model.__name__.lower()}.{offset + 1}@example.test"
                    ),
                    is_active=True,
                )
                existing.append(employee)
            elif not employee.is_active:
                employee.is_active = True
                employee.save(update_fields=["is_active", "updated_at"])
            selected.append(employee)
        return selected[0], selected[1]

    def _batch(
        self,
        *,
        agency: AgencyDimension,
        reporting_period: date,
        workbook_type: str,
        uploader: User | None,
        partial: bool,
        today: date,
    ) -> ImportBatch:
        key = f"{workbook_type}:{agency.code}:{reporting_period.isoformat()}"
        batch_id = _demo_uuid("batch", key)
        filename = (
            f"SUIVI ACCUEIL {agency.name}.xlsx"
            if workbook_type == ImportBatch.WorkbookType.TB1
            else f"Etat des en cours agences {reporting_period:%m-%y}.xlsx"
        )
        status = ImportBatch.Status.PARTIAL if partial else ImportBatch.Status.COMPLETED
        batch, _created = ImportBatch.objects.update_or_create(
            pk=batch_id,
            defaults={
                "original_filename": filename,
                "source_file": f"showcase/{batch_id}.xlsx",
                "workbook_type": workbook_type,
                "status": status,
                "checksum_sha256": hashlib.sha256(f"microcrd-showcase:{key}".encode()).hexdigest(),
                "file_size": 24_000 + int(agency.code or 0),
                "detected_agency": agency,
                "reporting_period": reporting_period,
                "sheet_name": (
                    f"{reporting_period:%m-%Y}"
                    if workbook_type == ImportBatch.WorkbookType.TB1
                    else agency.name
                ),
                "uploaded_by": uploader,
                "error_message": "",
            },
        )
        submitted_day = min(
            28,
            calendar.monthrange(reporting_period.year, reporting_period.month)[1],
            today.day
            if reporting_period.year == today.year and reporting_period.month == today.month
            else 28,
        )
        submitted_at = timezone.make_aware(
            datetime.combine(reporting_period.replace(day=submitted_day), time(hour=10))
        )
        ImportBatch.objects.filter(pk=batch.pk).update(
            created_at=submitted_at,
            updated_at=submitted_at + timedelta(minutes=4),
            started_at=submitted_at + timedelta(minutes=1),
            finished_at=submitted_at + timedelta(minutes=4),
        )
        return batch

    def _request(
        self,
        *,
        agency: AgencyDimension,
        agency_index: int,
        reporting_period: date,
        month_index: int,
        request_index: int,
        requests_per_month: int,
        tb1_batch: ImportBatch,
        tb2_batch: ImportBatch,
        ca_staff: tuple[CADimension | GPDimension, CADimension | GPDimension],
        gp_staff: tuple[CADimension | GPDimension, CADimension | GPDimension],
        credit_types: list[CreditTypeDimension],
        activities: list[ActivityDimension],
        request_types: list[RequestTypeDimension],
        rejection_reasons: list[RejectionReasonDimension],
        statuses: dict[str, StatusDimension],
        current_period: date,
    ) -> FactCreditRequest:
        day = 3 + request_index * max(1, 16 // max(requests_per_month - 1, 1))
        day = min(day, 24)
        request_date = reporting_period.replace(day=day)
        sequence = 70_000 + month_index * requests_per_month + request_index
        type_code = "R" if (agency_index + request_index) % 4 == 0 else "P"
        reference = f"{agency.code}/{sequence:05d}/{type_code}/{request_date:%d%m%Y}"
        amount = Decimal(1_500 + agency_index * 225 + month_index * 140 + request_index * 675)
        credit_type = credit_types[(agency_index + request_index) % len(credit_types)]
        activity = activities[(month_index + request_index + agency_index) % len(activities)]
        request_type = request_types[
            (agency_index + month_index + request_index) % len(request_types)
        ]
        ca = ca_staff[(month_index + request_index) % 2]
        gp = gp_staff[(month_index + request_index + agency_index) % 2]

        status_code = self._status_code(
            agency_index=agency_index,
            month_index=month_index,
            request_index=request_index,
            is_current=reporting_period == current_period,
        )
        reception = request_date + timedelta(days=1)
        assignment = (
            None if status_code == "awaiting_gp_assignment" else request_date + timedelta(days=2)
        )
        visit = (
            request_date + timedelta(days=4)
            if status_code not in {"awaiting_gp_assignment", "awaiting_visit"}
            else None
        )
        outcome = (
            request_date + timedelta(days=6 + agency_index % 5)
            if status_code in {"funded", "rejected"}
            else None
        )
        rejection_reason = (
            rejection_reasons[(agency_index + month_index + request_index) % len(rejection_reasons)]
            if status_code == "rejected"
            else None
        )

        row_number = request_index + 2
        tb1_row, _created = TB1RequestStagingRow.objects.update_or_create(
            pk=_demo_uuid("tb1", reference),
            defaults={
                "batch": tb1_batch,
                "agency": agency,
                "sheet_name": f"{reporting_period:%m-%Y}",
                "source_row": row_number,
                "reporting_period": reporting_period,
                "is_current": True,
                "row_hash": _row_hash("tb1", reference),
                "reference": reference,
                "validation_status": ValidationStatus.VALID,
                "match_status": MatchStatus.MATCHED,
                "amount": amount,
                "credit_type_name": credit_type.name,
                "request_type_name": request_type.name,
                "activity_name": activity.name,
                "request_date": request_date,
            },
        )
        tb2_row, _created = TB2SnapshotStagingRow.objects.update_or_create(
            pk=_demo_uuid("tb2", reference),
            defaults={
                "batch": tb2_batch,
                "agency": agency,
                "sheet_name": agency.name,
                "source_row": row_number,
                "reporting_period": reporting_period,
                "is_current": True,
                "row_hash": _row_hash("tb2", reference),
                "reference": reference,
                "validation_status": ValidationStatus.VALID,
                "match_status": MatchStatus.MATCHED,
                "amount": amount,
                "gp_name": str(gp.name) if assignment else "",
                "ca_name": str(ca.name),
                "received_at_agency_date": reception,
                "assigned_to_gp_date": assignment,
                "visit_date": visit,
                "disbursement_date": outcome if status_code == "funded" else None,
                "rejection_date": outcome if status_code == "rejected" else None,
                "rejection_reason": rejection_reason.name if rejection_reason else "",
                "matched_tb1": tb1_row,
            },
        )
        if tb1_row.matched_tb2_id != tb2_row.pk:
            tb1_row.matched_tb2 = tb2_row
            tb1_row.save(update_fields=["matched_tb2"])

        fact, _created = FactCreditRequest.objects.update_or_create(
            pk=_demo_uuid("fact", reference),
            defaults={
                "agency": agency,
                "gp": gp if assignment else None,
                "ca_caa": ca,
                "credit_type": credit_type,
                "activity": activity,
                "request_type": request_type,
                "status": statuses[status_code],
                "rejection_reason": rejection_reason,
                "reference": reference,
                "amount": amount,
                "request_date": _date_dimension(request_date),
                "reception_date": _date_dimension(reception),
                "gp_assignment_date": _date_dimension(assignment),
                "visit_date": _date_dimension(visit),
                "disbursement_date": _date_dimension(outcome) if status_code == "funded" else None,
                "rejection_date": _date_dimension(outcome) if status_code == "rejected" else None,
                "current_tb1_row": tb1_row,
                "current_tb2_row": tb2_row,
            },
        )
        self._history(fact, tb1_row, tb2_row, statuses)
        return fact

    @staticmethod
    def _status_code(
        *, agency_index: int, month_index: int, request_index: int, is_current: bool
    ) -> str:
        if is_current:
            return (
                "awaiting_gp_assignment",
                "awaiting_visit",
                "awaiting_decision",
                "funded",
                "rejected",
            )[request_index % 5]
        signature = (agency_index * 7 + month_index * 3 + request_index * 2) % 10
        if signature < 7:
            return "funded"
        if signature < 9:
            return "rejected"
        return "awaiting_decision"

    def _history(
        self,
        fact: FactCreditRequest,
        tb1_row: TB1RequestStagingRow,
        tb2_row: TB2SnapshotStagingRow,
        statuses: dict[str, StatusDimension],
    ) -> None:
        milestones: list[tuple[str, DateDimension | None, Model]] = [
            ("registered", fact.request_date, tb1_row),
        ]
        if fact.reception_date:
            reception_status = "received" if fact.gp_assignment_date else "awaiting_gp_assignment"
            milestones.append((reception_status, fact.reception_date, tb2_row))
        if fact.gp_assignment_date:
            milestones.append(("awaiting_visit", fact.gp_assignment_date, tb2_row))
        if fact.visit_date:
            milestones.append(("awaiting_decision", fact.visit_date, tb2_row))
        if fact.disbursement_date:
            milestones.append(("funded", fact.disbursement_date, tb2_row))
        if fact.rejection_date:
            milestones.append(("rejected", fact.rejection_date, tb2_row))
        for status_code, effective_date, source in milestones:
            if effective_date is None:
                continue
            CreditRequestStatusHistory.objects.get_or_create(
                pk=_demo_uuid("history", str(fact.pk), status_code),
                defaults={
                    "credit_request": fact,
                    "status": statuses[status_code],
                    "effective_date": effective_date,
                    "source_tb1_row": source if isinstance(source, TB1RequestStagingRow) else None,
                    "source_tb2_row": source if isinstance(source, TB2SnapshotStagingRow) else None,
                },
            )

    def _invalid_demo_row(
        self,
        batch: ImportBatch,
        agency: AgencyDimension,
        reporting_period: date,
    ) -> None:
        row, _created = TB1RequestStagingRow.objects.update_or_create(
            pk=_demo_uuid("invalid", str(batch.pk)),
            defaults={
                "batch": batch,
                "agency": agency,
                "sheet_name": f"{reporting_period:%m-%Y}",
                "source_row": 99,
                "reporting_period": reporting_period,
                "is_current": True,
                "row_hash": _row_hash("invalid", str(batch.pk)),
                "reference": "FORMAT-DEMO-INVALIDE",
                "validation_status": ValidationStatus.INVALID,
                "match_status": MatchStatus.BLOCKED,
                "amount": Decimal("-250"),
                "correction_values": {"amount": "-250"},
            },
        )
        DataQualityIssue.objects.update_or_create(
            pk=_demo_uuid("quality-issue", str(batch.pk)),
            defaults={
                "batch": batch,
                "tb1_row": row,
                "tb2_row": None,
                "severity": DataQualityIssue.Severity.ERROR,
                "code": "negative_amount",
                "field_name": "amount",
                "message": "Le montant doit être positif ou nul.",
                "details": {"expected": "positive_or_zero"},
            },
        )

    @staticmethod
    def _synchronize_batch_counts(batch_ids: set[uuid.UUID]) -> None:
        for batch in ImportBatch.objects.filter(pk__in=batch_ids):
            rows = (
                batch.tb1_request_rows.all()
                if batch.workbook_type == ImportBatch.WorkbookType.TB1
                else batch.tb2_snapshot_rows.all()
            )
            imported = rows.filter(
                validation_status=ValidationStatus.VALID,
                match_status=MatchStatus.MATCHED,
            ).count()
            rejected = rows.filter(validation_status=ValidationStatus.INVALID).count()
            batch.rows_discovered = rows.count()
            batch.rows_imported = imported
            batch.rows_rejected = rejected
            batch.status = ImportBatch.Status.PARTIAL if rejected else ImportBatch.Status.COMPLETED
            batch.save(
                update_fields=[
                    "rows_discovered",
                    "rows_imported",
                    "rows_rejected",
                    "status",
                    "updated_at",
                ]
            )

    def _seed_alerts(
        self,
        facts: list[FactCreditRequest],
        reporting_period: date,
    ) -> int:
        candidates = []
        for fact in facts:
            status = fact.status
            if status is not None and status.code in {
                "awaiting_gp_assignment",
                "awaiting_visit",
            }:
                candidates.append(fact)
        for fact in candidates:
            status = fact.status
            if status is None:
                continue
            reception_blocked = status.code == "awaiting_gp_assignment"
            rule = (
                DelayAlert.Rule.RECEPTION_BLOCKED
                if reception_blocked
                else DelayAlert.Rule.VISIT_BLOCKED
            )
            responsible = fact.ca_caa if reception_blocked else fact.gp
            DelayAlert.objects.update_or_create(
                credit_request=fact,
                rule=rule,
                defaults={
                    "agency": fact.agency,
                    "state": DelayAlert.State.NEW,
                    "reporting_period": reporting_period,
                    "started_on": self._alert_started_on(
                        fact,
                        reception_blocked=reception_blocked,
                        fallback=reporting_period,
                    ),
                    "responsible_role": "CA/CAA" if reception_blocked else "GP",
                    "responsible_name": str(responsible.name) if responsible else "",
                },
            )
        return len(candidates)

    @staticmethod
    def _alert_started_on(
        fact: FactCreditRequest, *, reception_blocked: bool, fallback: date
    ) -> date:
        if reception_blocked and fact.reception_date is not None:
            return fact.reception_date.calendar_date
        if fact.gp_assignment_date is not None:
            return fact.gp_assignment_date.calendar_date
        if fact.request_date is not None:
            return fact.request_date.calendar_date
        return fallback


def _demo_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(SHOWCASE_NAMESPACE, ":".join(parts))


def _row_hash(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()


def _date_dimension(value: date | None) -> DateDimension | None:
    if value is None:
        return None
    dimension, _created = DateDimension.objects.get_or_create(calendar_date=value)
    return dimension


def _add_months(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)
