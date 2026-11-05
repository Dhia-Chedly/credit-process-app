from typing import cast

from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.permissions import may_view_import_source_metadata
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
    CreditTypeDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
    StatusDimension,
)

FIELD_LABELS = {
    "agency": "Agence",
    "reference": "Référence de la demande",
    "request_date": "Date de la demande",
    "request_type": "Type de demande",
    "amount": "Montant demandé",
    "credit_type": "Type de crédit",
    "activity_category": "Catégorie d\u2019activité",
    "received_at_agency_date": "Date réception Chef d\u2019agence",
    "counsellor_name": "Nom du conseiller CA/CAA",
    "assigned_to_gp_date": "Date d\u2019affectation au GP",
    "gp_name": "Nom du GP",
    "visit_date": "DATE VISITE CLIENT",
    "status": "STATUT/ETAT DEMANDE",
    "outcome_date": "DATE DECAISSEMENT / DATE REJET",
    "rejection_reason": "Motif du rejet",
    "reporting_period": "Période déclarée",
}

ISSUE_PRESENTATION = {
    "missing_employee_identity": (
        "Employé obligatoire manquant",
        "Renseignez un employé actif de l\u2019agence, puis importez le classeur corrigé.",
    ),
    "unresolved_employee_identity": (
        "Employé introuvable ou inactif pour cette agence",
        "Ajoutez ou activez cet employé dans les référentiels, puis importez le classeur corrigé.",
    ),
    "missing_required_value": (
        "Valeur obligatoire manquante",
        "Renseignez la cellule obligatoire indiquée, puis importez le classeur corrigé.",
    ),
    "invalid_date": (
        "Date non reconnue",
        "Saisissez une date Excel valide dans la colonne indiquée.",
    ),
    "invalid_decimal": (
        "Montant non reconnu",
        "Saisissez un nombre valide, positif ou nul.",
    ),
    "negative_amount": (
        "Montant négatif interdit",
        "Remplacez le montant par une valeur positive ou nulle.",
    ),
    "invalid_lifecycle_sequence": (
        "Ordre des étapes incohérent",
        "Respectez l\u2019ordre réception, affectation GP, visite, puis résultat final.",
    ),
    "assignment_requires_reception": (
        "Affectation GP sans réception",
        "Renseignez la date de réception avant la date d\u2019affectation au GP.",
    ),
    "visit_requires_gp_assignment": (
        "Visite sans affectation GP",
        "Renseignez l\u2019affectation au GP avant la date de visite.",
    ),
    "terminal_status_requires_terminal_date": (
        "Date finale manquante",
        "Renseignez la date de décaissement ou de rejet correspondant au statut.",
    ),
    "terminal_date_requires_terminal_status": (
        "Statut final manquant ou incorrect",
        "Utilisez Décaissé ou Rejeté lorsqu\u2019une date finale est renseignée.",
    ),
    "rejected_status_requires_rejection_reason": (
        "Motif de rejet manquant",
        "Sélectionnez un motif de rejet approuvé.",
    ),
    "agency_cell_conflicts_with_source": (
        "Agence incohérente avec la feuille",
        "Alignez la valeur AGENCE sur le nom de la feuille.",
    ),
    "missing_agency": (
        "Agence inconnue ou inactive",
        "Vérifiez le nom du fichier ou de la feuille et le référentiel des agences.",
    ),
    "ambiguous_match": (
        "Rapprochement TB1/TB2 ambigu",
        "Corrigez les références en double avant de réimporter les classeurs.",
    ),
    "concurrent_publication_conflict": (
        "Dossier en cours de mise à jour",
        "Patientez quelques instants, puis réimportez le fichier.",
    ),
    "unresolved_dimension_value": (
        "Valeur non valide",
        "Utilisez une valeur active présente dans les référentiels.",
    ),
    "reference_must_be_text": (
        "Référence au mauvais format de cellule",
        "Formatez la cellule en Texte, saisissez la référence, puis réimportez le classeur.",
    ),
    "invalid_reference_format": (
        "Référence non valide",
        "Utilisez exactement CCCC/NNN/T/JJMMAAAA, par exemple 1234/001/P/20032026.",
    ),
    "reference_date_mismatch": (
        "Date de référence incohérente",
        "Utilisez dans la référence la même date que dans Date de la demande.",
    ),
    "reference_agency_code_mismatch": (
        "Code agence de référence non valide",
        "Utilisez le code à quatre chiffres configuré pour l\u2019agence de cette ligne.",
    ),
    "duplicate_reference_in_agency": (
        "Référence en double dans cette agence",
        "Conservez une seule ligne avec cette référence dans cet import.",
    ),
}

FIELD_EXPECTATIONS = {
    "agency": "Nom exact de l\u2019agence indiqué par le modèle et présent dans les référentiels.",
    "reference": "Texte exact : CCCC/NNN/T/JJMMAAAA, par exemple 1234/001/P/20032026.",
    "request_date": "Date Excel valide, par exemple 27/08/2026.",
    "request_type": "Type de demande présent dans les référentiels.",
    "amount": "Nombre positif ou nul, par exemple 15000 ou 15000,500.",
    "credit_type": "Type de crédit présent dans les référentiels.",
    "activity_category": "Catégorie d\u2019activité présente dans les référentiels.",
    "received_at_agency_date": "Date Excel valide, par exemple 27/08/2026.",
    "counsellor_name": "Nom exact d\u2019un CA/CAA actif rattaché à cette agence.",
    "assigned_to_gp_date": "Date Excel valide, par exemple 27/08/2026.",
    "gp_name": "Nom exact d\u2019un GP actif rattaché à cette agence.",
    "visit_date": "Date Excel valide, par exemple 27/08/2026.",
    "status": "Statut autorisé par le modèle ; pour une date finale : Décaissé ou Rejeté.",
    "outcome_date": "Date Excel valide, par exemple 27/08/2026.",
    "rejection_reason": "Motif de rejet présent dans les référentiels.",
}

STAGE_VALUE_FIELDS = {
    "amount": "amount",
    "credit_type": "credit_type_name",
    "request_type": "request_type_name",
    "activity_category": "activity_name",
    "request_date": "request_date",
    "counsellor_name": "ca_name",
    "gp_name": "gp_name",
    "received_at_agency_date": "received_at_agency_date",
    "assigned_to_gp_date": "assigned_to_gp_date",
    "visit_date": "visit_date",
    "rejection_reason": "rejection_reason",
}

DIMENSION_VALUE_MODELS: dict[
    str,
    type[CreditTypeDimension]
    | type[ActivityDimension]
    | type[RequestTypeDimension]
    | type[StatusDimension]
    | type[RejectionReasonDimension],
] = {
    "credit_type": CreditTypeDimension,
    "activity_category": ActivityDimension,
    "request_type": RequestTypeDimension,
    "status": StatusDimension,
    "rejection_reason": RejectionReasonDimension,
}

ROW_DISPLAY_ORDER = {
    "tb1": (
        "reference",
        "request_date",
        "request_type",
        "amount",
        "credit_type",
        "activity_category",
    ),
    "tb2": (
        "agency",
        "reference",
        "request_date",
        "request_type",
        "amount",
        "received_at_agency_date",
        "counsellor_name",
        "assigned_to_gp_date",
        "gp_name",
        "visit_date",
        "status",
        "outcome_date",
        "rejection_reason",
    ),
}


def _may_view_source_metadata(context: dict[str, object]) -> bool:
    request = context.get("request")
    return may_view_import_source_metadata(getattr(request, "user", None))


class WorkbookUploadSerializer(serializers.Serializer[dict[str, UploadedFile]]):
    file = serializers.FileField(write_only=True)


class ImportBatchSerializer(serializers.ModelSerializer[ImportBatch]):
    original_filename = serializers.SerializerMethodField()
    discovered_count = serializers.IntegerField(source="rows_discovered", read_only=True)
    valid_staged_count = serializers.SerializerMethodField()
    quarantined_count = serializers.SerializerMethodField()
    unmatched_count = serializers.SerializerMethodField()
    published_or_updated_count = serializers.SerializerMethodField()
    error_message = serializers.CharField(read_only=True)
    detected_agency = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = (
            "id",
            "original_filename",
            "workbook_type",
            "status",
            "file_size",
            "checksum_sha256",
            "detected_agency",
            "reporting_period",
            "discovered_count",
            "valid_staged_count",
            "quarantined_count",
            "unmatched_count",
            "published_or_updated_count",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields

    def get_detected_agency(self, obj: ImportBatch) -> dict[str, str] | None:
        if obj.detected_agency is None:
            return None
        return {"name": obj.detected_agency.name}

    def _stage_counts(self, obj: ImportBatch) -> dict[str, int]:
        """Count the actual staging states instead of reusing publication totals."""

        cache = cast(dict[object, dict[str, int]], getattr(self, "_stage_counts_cache", {}))
        if obj.pk in cache:
            return cache[obj.pk]
        models = (TB1RequestStagingRow, TB2SnapshotStagingRow)
        valid = sum(
            model.objects.filter(batch=obj, validation_status=ValidationStatus.VALID)
            .exclude(match_status=MatchStatus.BLOCKED)
            .count()
            for model in models
        )
        quarantined = sum(
            model.objects.filter(batch=obj)
            .filter(
                Q(validation_status=ValidationStatus.INVALID) | Q(match_status=MatchStatus.BLOCKED)
            )
            .count()
            for model in models
        )
        unmatched = sum(
            model.objects.filter(
                batch=obj,
                validation_status=ValidationStatus.VALID,
                match_status=MatchStatus.UNMATCHED,
            ).count()
            for model in models
        )
        published = sum(
            model.objects.filter(
                batch=obj,
                validation_status=ValidationStatus.VALID,
                match_status=MatchStatus.MATCHED,
            ).count()
            for model in models
        )
        counts = {
            "valid_staged": valid,
            "quarantined": max(quarantined, obj.rows_rejected),
            "unmatched": unmatched,
            "published_or_updated": published,
        }
        cache[obj.pk] = counts
        self._stage_counts_cache = cache
        return counts

    def get_valid_staged_count(self, obj: ImportBatch) -> int:
        return self._stage_counts(obj)["valid_staged"]

    def get_quarantined_count(self, obj: ImportBatch) -> int:
        return self._stage_counts(obj)["quarantined"]

    def get_unmatched_count(self, obj: ImportBatch) -> int:
        return self._stage_counts(obj)["unmatched"]

    def get_published_or_updated_count(self, obj: ImportBatch) -> int:
        return self._stage_counts(obj)["published_or_updated"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_original_filename(self, obj: ImportBatch) -> str | None:
        if not _may_view_source_metadata(self.context):
            return None
        return obj.original_filename


class DataQualityIssueSerializer(serializers.ModelSerializer[DataQualityIssue]):
    """Expose review metadata without returning protected workbook row data."""

    sheet_name = serializers.SerializerMethodField()
    source_row = serializers.SerializerMethodField()
    field_label = serializers.SerializerMethodField()
    user_title = serializers.SerializerMethodField()
    required_correction = serializers.SerializerMethodField()
    submitted_value = serializers.SerializerMethodField()
    expected_format = serializers.SerializerMethodField()
    row_values = serializers.SerializerMethodField()
    action_kind = serializers.SerializerMethodField()

    class Meta:
        model = DataQualityIssue
        fields = (
            "id",
            "severity",
            "code",
            "field_name",
            "field_label",
            "message",
            "user_title",
            "required_correction",
            "submitted_value",
            "expected_format",
            "row_values",
            "action_kind",
            "sheet_name",
            "source_row",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_sheet_name(self, obj: DataQualityIssue) -> str | None:
        row = obj.tb1_row or obj.tb2_row
        if not _may_view_source_metadata(self.context):
            return None
        if row is None:
            value = obj.details.get("sheet_name")
            return str(value) if value else None
        return row.sheet_name or row.batch.sheet_name or None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_source_row(self, obj: DataQualityIssue) -> int | None:
        row = obj.tb1_row or obj.tb2_row
        if row is not None:
            return row.source_row
        value = obj.details.get("source_row")
        return value if isinstance(value, int) else None

    @extend_schema_field(serializers.CharField())
    def get_field_label(self, obj: DataQualityIssue) -> str:
        return FIELD_LABELS.get(obj.field_name, obj.field_name or "Classeur")

    @extend_schema_field(serializers.CharField())
    def get_user_title(self, obj: DataQualityIssue) -> str:
        if obj.code in {"missing_employee_identity", "unresolved_employee_identity"}:
            role = "CA/CAA" if obj.field_name == "counsellor_name" else "GP"
            qualifier = (
                "obligatoire manquant"
                if obj.code == "missing_employee_identity"
                else "introuvable ou inactif pour cette agence"
            )
            return f"{role} {qualifier}"
        return ISSUE_PRESENTATION.get(obj.code, ("Correction requise", ""))[0]

    @extend_schema_field(serializers.CharField())
    def get_required_correction(self, obj: DataQualityIssue) -> str:
        return ISSUE_PRESENTATION.get(
            obj.code,
            (
                "Correction requise",
                "Corrigez la colonne indiquée en suivant le modèle officiel, puis "
                "réimportez le fichier.",
            ),
        )[1]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_submitted_value(self, obj: DataQualityIssue) -> str | None:
        if obj.field_name not in FIELD_EXPECTATIONS:
            return None
        if "submitted_value" in obj.details:
            return str(obj.details["submitted_value"])
        row = obj.tb1_row or obj.tb2_row
        if row is not None and obj.field_name in row.correction_values:
            value = row.correction_values[obj.field_name]
            return "" if value is None else str(value)
        attribute = STAGE_VALUE_FIELDS.get(obj.field_name)
        if row is None or attribute is None or not hasattr(row, attribute):
            return None
        value = getattr(row, attribute)
        if value is None:
            return ""
        return str(value)

    @extend_schema_field(serializers.CharField())
    def get_expected_format(self, obj: DataQualityIssue) -> str:
        model = DIMENSION_VALUE_MODELS.get(obj.field_name)
        if model is not None:
            cache = getattr(self, "_dimension_values_cache", {})
            if obj.field_name not in cache:
                cache[obj.field_name] = list(
                    model.objects.filter(is_active=True)
                    .order_by("name")
                    .values_list("name", flat=True)
                )
                self._dimension_values_cache = cache
            values = cache[obj.field_name]
            if values:
                return f"Valeurs autorisées : {', '.join(values)}."
        return FIELD_EXPECTATIONS.get(
            obj.field_name,
            "Valeur conforme à la colonne correspondante du modèle officiel.",
        )

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_row_values(self, obj: DataQualityIssue) -> list[dict[str, str | None]]:
        row = obj.tb1_row or obj.tb2_row
        if row is None:
            kind = obj.details.get("source_kind")
            values = obj.details.get("row_values")
            if kind not in ROW_DISPLAY_ORDER or not isinstance(values, dict):
                return []
            correction_values = values
        else:
            kind = "tb1" if obj.tb1_row_id is not None else "tb2"
            correction_values = row.correction_values
        return [
            {
                "field_name": field_name,
                "field_label": FIELD_LABELS[field_name],
                "value": (
                    None
                    if correction_values.get(field_name) is None
                    else str(correction_values[field_name])
                ),
            }
            for field_name in ROW_DISPLAY_ORDER[kind]
        ]

    @extend_schema_field(serializers.CharField())
    def get_action_kind(self, obj: DataQualityIssue) -> str:
        if obj.field_name == "counsellor_name":
            return "reference_ca"
        if obj.field_name == "gp_name":
            return "reference_gp"
        if obj.code in {"ambiguous_match", "missing_match_key"}:
            return "matching"
        return "template"
