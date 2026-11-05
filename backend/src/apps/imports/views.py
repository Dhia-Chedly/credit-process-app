from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from kombu.exceptions import KombuError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.accounts.models import User
from apps.core.permissions import ImportBatchPermission
from apps.data_quality.models import DataQualityIssue
from apps.imports.models import ImportBatch, TB1RequestStagingRow, TB2SnapshotStagingRow
from apps.imports.serializers import (
    DataQualityIssueSerializer,
    ImportBatchSerializer,
    WorkbookUploadSerializer,
)
from apps.imports.tasks import process_import_batch
from apps.imports.uploads import UploadRejectedError, inspect_xlsx_upload


class ImportBatchViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet[ImportBatch],
):
    permission_classes = [ImportBatchPermission]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ("status", "workbook_type", "detected_agency", "reporting_period")
    queryset = ImportBatch.objects.select_related("detected_agency", "uploaded_by").all()

    def get_queryset(self) -> QuerySet[ImportBatch]:
        queryset = super().get_queryset()
        return queryset if isinstance(self.request.user, User) else queryset.none()

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        if self.action == "create":
            return WorkbookUploadSerializer
        if self.action == "issues":
            return DataQualityIssueSerializer
        return ImportBatchSerializer

    @extend_schema(
        request=WorkbookUploadSerializer,
        responses={200: ImportBatchSerializer, 202: ImportBatchSerializer},
    )
    def create(self, request: Request, *_args: Any, **_kwargs: Any) -> Response:
        upload_serializer = WorkbookUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        upload = upload_serializer.validated_data["file"]

        try:
            inspection = inspect_xlsx_upload(
                upload,
                max_upload_bytes=settings.IMPORT_MAX_UPLOAD_BYTES,
                max_uncompressed_bytes=settings.IMPORT_MAX_UNCOMPRESSED_BYTES,
            )
        except UploadRejectedError as exc:
            return Response(
                {"code": exc.code, "file": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = ImportBatch.objects.filter(checksum_sha256=inspection.sha256).first()
        if existing is not None:
            if existing.status == ImportBatch.Status.PARTIAL and existing.rows_imported == 0:
                return self._retry_duplicate_upload(existing, upload, inspection.original_filename)
            if (
                existing.status == ImportBatch.Status.FAILED
                and not existing.tb1_request_rows.exists()
                and not existing.tb2_snapshot_rows.exists()
            ):
                return self._retry_duplicate_upload(existing, upload, inspection.original_filename)
            return self._duplicate_response(existing)

        uploaded_by = request.user if isinstance(request.user, User) else None
        stored_file_name = ""
        try:
            with transaction.atomic():
                batch, created = ImportBatch.objects.get_or_create(
                    checksum_sha256=inspection.sha256,
                    defaults={
                        "original_filename": inspection.original_filename,
                        "source_file": "",
                        "file_size": inspection.size,
                        "status": ImportBatch.Status.UPLOADED,
                        "uploaded_by": uploaded_by,
                    },
                )
                if created:
                    batch.source_file.save(inspection.original_filename, upload, save=False)
                    stored_file_name = batch.source_file.name
                    batch.status = ImportBatch.Status.QUEUED
                    batch.save(update_fields=["source_file", "status", "updated_at"])
        except Exception:
            if stored_file_name:
                default_storage.delete(stored_file_name)
            raise

        if not created:
            return self._duplicate_response(batch)

        if not self._enqueue(batch):
            return Response(
                self._batch_data(batch),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(self._batch_data(batch), status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses={202: ImportBatchSerializer})
    @action(detail=True, methods=["post"])
    def retry(self, _request: Request, pk: str | None = None) -> Response:
        _ = pk
        batch = self.get_object()
        if batch.status != ImportBatch.Status.FAILED:
            return Response(
                {"detail": "Only failed imports can be retried."},
                status=status.HTTP_409_CONFLICT,
            )
        if batch.tb1_request_rows.exists() or batch.tb2_snapshot_rows.exists():
            return Response(
                {
                    "detail": (
                        "This batch has published import evidence and requires governed "
                        "canonical reconciliation before replay."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        batch.status = ImportBatch.Status.QUEUED
        batch.error_message = ""
        batch.finished_at = None
        batch.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        if not self._enqueue(batch):
            return Response(
                self._batch_data(batch),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(self._batch_data(batch), status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={200: DataQualityIssueSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def issues(self, _request: Request, pk: str | None = None) -> Response:
        _ = pk
        batch = self.get_object()
        queryset = DataQualityIssue.objects.filter(batch=batch).select_related(
            "tb1_row",
            "tb2_row",
        )
        page = self.paginate_queryset(queryset)  # type: ignore[arg-type]
        if page is not None:
            serializer = DataQualityIssueSerializer(
                page,
                many=True,
                context=self.get_serializer_context(),
            )
            return self.get_paginated_response(serializer.data)

        serializer = DataQualityIssueSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @staticmethod
    def _enqueue(batch: ImportBatch) -> bool:
        try:
            process_import_batch.delay(str(batch.pk))
        except (KombuError, OSError):
            batch.status = ImportBatch.Status.FAILED
            batch.error_message = "The import worker queue is temporarily unavailable."
            batch.finished_at = timezone.now()
            batch.save(
                update_fields=[
                    "status",
                    "error_message",
                    "finished_at",
                    "updated_at",
                ]
            )
            return False
        return True

    def _duplicate_response(self, batch: ImportBatch) -> Response:
        if not self.get_queryset().filter(pk=batch.pk).exists():
            response = Response(
                {
                    "code": "duplicate_import",
                    "detail": "This workbook has already been uploaded.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        else:
            data = self._batch_data(batch)
            data["duplicate"] = True
            response = Response(data, status=status.HTTP_200_OK)
        response["X-Import-Duplicate"] = "true"
        return response

    def _retry_duplicate_upload(
        self,
        batch: ImportBatch,
        upload: Any,
        original_filename: str,
    ) -> Response:
        """Reprocess an unchanged upload after a safe-to-retry failed or partial run."""

        old_file_name = batch.source_file.name
        with transaction.atomic():
            TB1RequestStagingRow.objects.filter(batch=batch).delete()
            TB2SnapshotStagingRow.objects.filter(batch=batch).delete()
            DataQualityIssue.objects.filter(batch=batch).delete()
            batch.source_file.save(original_filename, upload, save=False)
            batch.status = ImportBatch.Status.QUEUED
            batch.rows_discovered = 0
            batch.rows_imported = 0
            batch.rows_rejected = 0
            batch.started_at = None
            batch.finished_at = None
            batch.error_message = ""
            batch.save(
                update_fields=[
                    "source_file",
                    "status",
                    "rows_discovered",
                    "rows_imported",
                    "rows_rejected",
                    "started_at",
                    "finished_at",
                    "error_message",
                    "updated_at",
                ]
            )
        if old_file_name and old_file_name != batch.source_file.name:
            default_storage.delete(old_file_name)
        if not self._enqueue(batch):
            return Response(self._batch_data(batch), status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self._batch_data(batch), status=status.HTTP_202_ACCEPTED)

    def _batch_data(self, batch: ImportBatch) -> dict[str, object]:
        return dict(ImportBatchSerializer(batch, context=self.get_serializer_context()).data)
