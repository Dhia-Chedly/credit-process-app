from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReferenceDataPermission
from apps.warehouse.crypto import normalize_match_value
from apps.warehouse.models import (
    AgencyDimension,
    CADimension,
    FactCreditRequest,
    GPDimension,
    SelectableDimension,
    StaffDimension,
)
from apps.warehouse.serializers import (
    SELECTABLE_REFERENCE_MODELS,
    AgencyCodeUpdateSerializer,
    AgencyCreateSerializer,
    AgencyReferenceSerializer,
    EmployeeCreateSerializer,
    EmployeeReferenceSerializer,
    EmployeeUpdateSerializer,
    SelectableReferenceCreateSerializer,
    SelectableReferenceSerializer,
)


def _employee_payload(employee: StaffDimension, *, role: str) -> dict[str, Any]:
    return {
        "id": employee.id,
        "name": employee.name,
        "email": employee.email,
        "agency_id": employee.agency_id,
        "role": role,
        "is_active": employee.is_active,
        "usage_count": _usage_count(employee),
    }


def _deactivate(instance: AgencyDimension | StaffDimension) -> dict[str, str]:
    instance.is_active = False
    instance.save(update_fields=["is_active", "updated_at"])
    return {"action": "deactivated", "name": instance.name}


SELECTABLE_FACT_FIELDS: dict[str, str] = {
    "credit-types": "credit_type",
    "activities": "activity",
    "request-types": "request_type",
    "rejection-reasons": "rejection_reason",
}


def _usage_count(instance: AgencyDimension | StaffDimension | SelectableDimension) -> int:
    if isinstance(instance, AgencyDimension):
        return FactCreditRequest.objects.filter(agency=instance).count()
    if isinstance(instance, CADimension):
        return FactCreditRequest.objects.filter(ca_caa=instance).count()
    if isinstance(instance, GPDimension):
        return FactCreditRequest.objects.filter(gp=instance).count()
    field = next(
        (
            value
            for key, value in SELECTABLE_FACT_FIELDS.items()
            if isinstance(instance, SELECTABLE_REFERENCE_MODELS[key])
        ),
        None,
    )
    return FactCreditRequest.objects.filter(**{field: instance}).count() if field else 0


def _selectable_payload(instance: SelectableDimension) -> dict[str, object]:
    return {
        "id": str(instance.pk),
        "name": instance.name,
        "is_active": instance.is_active,
        "usage_count": _usage_count(instance),
    }


def _inactive_agency_with_name(name: str) -> AgencyDimension | None:
    normalized = normalize_match_value(name)
    return next(
        (
            agency
            for agency in AgencyDimension.objects.filter(is_active=False)
            if normalize_match_value(agency.name) == normalized
        ),
        None,
    )


def _inactive_employee_with_name(
    *, agency: AgencyDimension, name: str, model: type[CADimension] | type[GPDimension]
) -> CADimension | GPDimension | None:
    normalized = normalize_match_value(name)
    return next(
        (
            employee
            for employee in model.objects.filter(agency=agency, is_active=False)
            if normalize_match_value(employee.name) == normalized
        ),
        None,
    )


class ReferenceDataView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(responses={200: None})
    def get(self, _request: Request) -> Response:
        agencies = AgencyDimension.objects.all().order_by("name")
        cas = [
            _employee_payload(employee, role="ca")
            for employee in CADimension.objects.select_related("agency")
        ]
        gps = [
            _employee_payload(employee, role="gp")
            for employee in GPDimension.objects.select_related("agency")
        ]
        cas.sort(key=lambda employee: str(employee["name"]).casefold())
        gps.sort(key=lambda employee: str(employee["name"]).casefold())
        return Response(
            {
                "agencies": [
                    {
                        **AgencyReferenceSerializer(agency).data,
                        "usage_count": _usage_count(agency),
                    }
                    for agency in agencies
                ],
                "employees": {
                    "ca": cas,
                    "gp": gps,
                },
                "dimensions": {
                    kind: [
                        _selectable_payload(item) for item in model.objects.all().order_by("name")
                    ]
                    for kind, model in SELECTABLE_REFERENCE_MODELS.items()
                },
            }
        )


class AgencyReferenceCollectionView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(
        request=AgencyCreateSerializer,
        responses={200: AgencyReferenceSerializer, 201: AgencyReferenceSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = AgencyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        code = serializer.validated_data["code"]
        agency = _inactive_agency_with_name(name)
        if agency is not None:
            agency.is_active = True
            agency.code = code
            agency.save(update_fields=["is_active", "code", "updated_at"])
            return Response(AgencyReferenceSerializer(agency).data)
        agency = AgencyDimension.objects.create(name=name, code=code)
        return Response(AgencyReferenceSerializer(agency).data, status=status.HTTP_201_CREATED)


class AgencyReferenceDetailView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(request=AgencyCodeUpdateSerializer, responses={200: AgencyReferenceSerializer})
    def patch(self, request: Request, pk: str) -> Response:
        agency = get_object_or_404(AgencyDimension, pk=pk)
        serializer = AgencyCodeUpdateSerializer(agency, data=request.data)  # type: ignore[arg-type]
        serializer.is_valid(raise_exception=True)
        for attribute, value in serializer.validated_data.items():
            setattr(agency, attribute, value)
        agency.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        return Response(AgencyReferenceSerializer(agency).data)

    @extend_schema(responses={200: None})
    def delete(self, _request: Request, pk: str) -> Response:
        agency = get_object_or_404(AgencyDimension, pk=pk, is_active=True)
        return Response(_deactivate(agency))


class EmployeeReferenceCollectionView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(
        request=EmployeeCreateSerializer,
        responses={200: EmployeeReferenceSerializer, 201: EmployeeReferenceSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        model = CADimension if role == "ca" else GPDimension
        agency = serializer.validated_data["agency"]
        name = serializer.validated_data["name"]
        employee = _inactive_employee_with_name(agency=agency, name=name, model=model)
        reactivated = employee is not None
        if employee is not None:
            employee.is_active = True
            employee.email = serializer.validated_data.get("email", employee.email)
            employee.save(update_fields=["is_active", "email", "updated_at"])
        else:
            employee = model.objects.create(
                agency=agency, name=name, email=serializer.validated_data.get("email", "")
            )
        return Response(
            EmployeeReferenceSerializer(_employee_payload(employee, role=role)).data,
            status=status.HTTP_200_OK if reactivated else status.HTTP_201_CREATED,
        )


class EmployeeReferenceDetailView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(responses={200: None})
    def delete(self, _request: Request, role: str, pk: str) -> Response:
        model = CADimension if role == "ca" else GPDimension if role == "gp" else None
        if model is None:
            return Response({"detail": "Unknown employee role."}, status=status.HTTP_404_NOT_FOUND)
        employee = get_object_or_404(model, pk=pk, is_active=True)
        return Response(_deactivate(employee))

    @extend_schema(request=EmployeeUpdateSerializer, responses={200: EmployeeReferenceSerializer})
    def patch(self, request: Request, role: str, pk: str) -> Response:
        model = CADimension if role == "ca" else GPDimension if role == "gp" else None
        if model is None:
            return Response({"detail": "Unknown employee role."}, status=status.HTTP_404_NOT_FOUND)
        employee = get_object_or_404(model, pk=pk)
        serializer = EmployeeUpdateSerializer(employee, data=request.data)  # type: ignore[arg-type]
        serializer.is_valid(raise_exception=True)
        for attribute, value in serializer.validated_data.items():
            setattr(employee, attribute, value)
        employee.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        return Response(EmployeeReferenceSerializer(_employee_payload(employee, role=role)).data)


class SelectableReferenceCollectionView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(
        request=SelectableReferenceCreateSerializer,
        responses={200: SelectableReferenceSerializer, 201: SelectableReferenceSerializer},
    )
    def post(self, request: Request, kind: str) -> Response:
        model = SELECTABLE_REFERENCE_MODELS.get(kind)
        if model is None:
            return Response({"detail": "Unknown reference type."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SelectableReferenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        existing = next(
            (
                item
                for item in model.objects.all()
                if normalize_match_value(item.name) == normalize_match_value(name)
            ),
            None,
        )
        if existing is not None:
            if existing.is_active:
                return Response(
                    {"name": ["This value already exists."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            existing.is_active = True
            existing.save(update_fields=["is_active", "updated_at"])
            return Response(SelectableReferenceSerializer(existing).data)
        item = model.objects.create(name=name)
        return Response(SelectableReferenceSerializer(item).data, status=status.HTTP_201_CREATED)


class SelectableReferenceDetailView(APIView):
    permission_classes = [ReferenceDataPermission]

    @extend_schema(
        request=inline_serializer(
            name="SelectableReferenceUpdate",
            fields={"is_active": serializers.BooleanField()},
        ),
        responses={200: SelectableReferenceSerializer},
    )
    def patch(self, request: Request, kind: str, pk: str) -> Response:
        model = SELECTABLE_REFERENCE_MODELS.get(kind)
        if model is None:
            return Response({"detail": "Unknown reference type."}, status=status.HTTP_404_NOT_FOUND)
        item = get_object_or_404(model, pk=pk)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return Response(
                {"is_active": ["Provide true or false."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.is_active = is_active
        item.save(update_fields=["is_active", "updated_at"])
        return Response(SelectableReferenceSerializer(item).data)
