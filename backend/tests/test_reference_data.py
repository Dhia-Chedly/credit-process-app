from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.analytics.services import AnalyticsFilters, _agency_catalog
from apps.warehouse.models import AgencyDimension, CreditTypeDimension


@pytest.fixture
def operator_client() -> APIClient:
    user = User.objects.create_user(
        username="operator",
        password="secure-test-password",
        is_reference_admin=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_active_operator_can_create_and_list_agency_staff_reference_data(
    operator_client: APIClient,
) -> None:
    agency_response = operator_client.post(
        reverse("warehouse:reference-agencies"),
        {"name": "Tunis Centre", "code": "9991"},
        format="json",
    )

    assert agency_response.status_code == 201
    agency_id = agency_response.data["id"]

    ca_response = operator_client.post(
        reverse("warehouse:reference-employees"),
        {"name": "Amina Ben Salah", "agency_id": agency_id, "role": "ca"},
        format="json",
    )
    gp_response = operator_client.post(
        reverse("warehouse:reference-employees"),
        {"name": "Karim Trabelsi", "agency_id": agency_id, "role": "gp"},
        format="json",
    )

    assert ca_response.status_code == 201
    assert ca_response.data["name"] == "Amina Ben Salah"
    assert ca_response.data["agency_id"] == str(agency_id)
    assert ca_response.data["role"] == "ca"
    assert gp_response.status_code == 201

    response = operator_client.get(reverse("warehouse:reference-data"))

    assert response.status_code == 200
    assert response.data["agencies"] == [
        {
            "id": str(agency_id),
            "name": "Tunis Centre",
            "code": "9991",
            "is_active": True,
            "usage_count": 0,
        }
    ]
    assert [employee["name"] for employee in response.data["employees"]["ca"]] == [
        "Amina Ben Salah"
    ]
    assert [employee["name"] for employee in response.data["employees"]["gp"]] == ["Karim Trabelsi"]


@pytest.mark.django_db
def test_reference_data_rejects_normalized_duplicates_and_reserved_unknown(
    operator_client: APIClient,
) -> None:
    agency_response = operator_client.post(
        reverse("warehouse:reference-agencies"),
        {"name": "Tunis-Centre", "code": "9992"},
        format="json",
    )
    agency_id = agency_response.data["id"]

    duplicate_agency = operator_client.post(
        reverse("warehouse:reference-agencies"),
        {"name": "tunis centre", "code": "9993"},
        format="json",
    )
    first_gp = operator_client.post(
        reverse("warehouse:reference-employees"),
        {"name": "Mohamed A. Ali", "agency_id": agency_id, "role": "gp"},
        format="json",
    )
    duplicate_gp = operator_client.post(
        reverse("warehouse:reference-employees"),
        {"name": "mohamed a ali", "agency_id": agency_id, "role": "gp"},
        format="json",
    )
    unknown = operator_client.post(
        reverse("warehouse:reference-employees"),
        {"name": "Inconnu", "agency_id": agency_id, "role": "ca"},
        format="json",
    )

    assert first_gp.status_code == 201
    assert duplicate_agency.status_code == 400
    assert "name" in duplicate_agency.data
    assert duplicate_gp.status_code == 400
    assert "name" in duplicate_gp.data
    assert unknown.status_code == 400
    assert "name" in unknown.data


def test_reference_data_requires_authentication() -> None:
    response = APIClient().get(reverse("warehouse:reference-data"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_reference_admin_can_deactivate_and_reactivate_controlled_values(
    operator_client: APIClient,
) -> None:
    create = operator_client.post(
        reverse("warehouse:reference-dimension-collection", kwargs={"kind": "credit-types"}),
        {"name": "Crédit saisonnier"},
        format="json",
    )

    assert create.status_code == 201
    item_id = create.data["id"]
    detail = reverse(
        "warehouse:reference-dimension-detail",
        kwargs={"kind": "credit-types", "pk": item_id},
    )
    deactivated = operator_client.patch(detail, {"is_active": False}, format="json")
    assert deactivated.data["is_active"] is False
    reactivated = operator_client.post(
        reverse("warehouse:reference-dimension-collection", kwargs={"kind": "credit-types"}),
        {"name": "credit saisonnier"},
        format="json",
    )

    assert reactivated.status_code == 200
    assert reactivated.data["is_active"] is True
    assert CreditTypeDimension.objects.get(pk=item_id).is_active is True


@pytest.mark.django_db
def test_inactive_agencies_remain_available_to_historical_analytics_catalog() -> None:
    agency = AgencyDimension.objects.create(name="Agence historique", code="9876", is_active=False)

    catalog = _agency_catalog(
        AnalyticsFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 1), agency_ids=())
    )

    assert str(agency.pk) in catalog


@pytest.mark.django_db
def test_non_reference_admin_cannot_manage_reference_data() -> None:
    user = User.objects.create_user(username="operator", password="secure-test-password")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(reverse("warehouse:reference-data"))

    assert response.status_code == 403
