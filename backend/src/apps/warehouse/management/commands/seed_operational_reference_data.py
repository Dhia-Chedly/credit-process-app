from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.warehouse.crypto import normalize_match_value
from apps.warehouse.models import (
    ActivityDimension,
    AgencyDimension,
    CADimension,
    CreditTypeDimension,
    GPDimension,
    RejectionReasonDimension,
    RequestTypeDimension,
)

AGENCIES = (
    "ARIANA",
    "BEJA",
    "BEN AROUS",
    "BIZERTE",
    "DJERBA",
    "EZZAHROUNI",
    "FAHS",
    "GABES",
    "GAFSA",
    "JENDOUBA",
    "KASSERINE",
    "KEF",
    "MAHDIA",
    "NABEUL",
    "SFAX",
    "SIDI BOUZID",
    "SILIANA",
    "SOUSSE",
    "TCV",
    "TOZEUR",
)

# Codes evidenced by the majority reference pattern for each agency worksheet
# in the supplied historic ``Etat des en cours`` workbooks.
AGENCY_CODES = {
    "ARIANA": "1200",
    "BEJA": "1300",
    "BEN AROUS": "1100",
    "BIZERTE": "2900",
    "DJERBA": "2800",
    "EZZAHROUNI": "1000",
    "FAHS": "2300",
    "GABES": "2700",
    "GAFSA": "1500",
    "JENDOUBA": "1600",
    "KASSERINE": "2400",
    "KEF": "1900",
    "MAHDIA": "3000",
    "NABEUL": "2600",
    "SFAX": "1700",
    "SIDI BOUZID": "2000",
    "SILIANA": "2500",
    "SOUSSE": "2100",
    "TCV": "1400",
    "TOZEUR": "1800",
}
CREDIT_TYPES = ("Microcrédit", "ACV", "TPE", "TPME")

ACTIVITIES = ("Commerce", "Agriculture", "Artisanat", "Services", "Autres")

REQUEST_TYPES = ("Nouvelle demande", "Renouvellement")
REJECTION_REASONS = (
    "Capacité insuffisante",
    "Endettement élevé",
    "Impayés",
    "Projet inexistant",
    "Activité non viable",
    "Garantie insuffisante",
    "Dossier incomplet",
    "Détournement de crédit",
    "Plafond dépassé",
    "Cession refusée",
    "Demande retirée",
    "Conditions refusées",
    "Autre",
)


class Command(BaseCommand):
    help = "Seed approved agencies and controlled operational taxonomies."

    def handle(self, *_args: Any, **_options: Any) -> None:
        with transaction.atomic():
            for name in AGENCIES:
                defaults: dict[str, object] = {"is_active": True}
                if name in AGENCY_CODES:
                    defaults["code"] = AGENCY_CODES[name]
                AgencyDimension.objects.update_or_create(name=name, defaults=defaults)
            self._seed_dimensions(CreditTypeDimension, CREDIT_TYPES)
            self._seed_dimensions(ActivityDimension, ACTIVITIES)
            self._seed_dimensions(RequestTypeDimension, REQUEST_TYPES)
            self._deactivate_legacy_unknown_staff()
            for name in REJECTION_REASONS:
                RejectionReasonDimension.objects.update_or_create(
                    name=name,
                    defaults={"is_active": True},
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded 20 agencies, 4 credit types, 5 activities, 2 request types, "
                "and 13 rejection reasons."
            )
        )

    @staticmethod
    def _seed_dimensions(
        model: type[CreditTypeDimension] | type[ActivityDimension] | type[RequestTypeDimension],
        values: tuple[str, ...],
    ) -> None:
        for name in values:
            model.objects.update_or_create(
                name=name,
                defaults={"is_active": True},
            )

    @staticmethod
    def _deactivate_legacy_unknown_staff() -> None:
        for model in (CADimension, GPDimension):
            for employee in model.objects.filter(is_active=True):
                if normalize_match_value(employee.name) in {
                    normalize_match_value("Inconnu"),
                    normalize_match_value("Unknown"),
                }:
                    employee.is_active = False
                    employee.save(update_fields=["is_active", "updated_at"])
