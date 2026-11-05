from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def test_live_health_is_public(api_client: APIClient) -> None:
    response = api_client.get(reverse("health:live"))

    assert response.status_code == 200
    assert response.json() == {"service": "microcrd-api", "status": "ok"}


@pytest.mark.django_db
def test_ready_health_checks_database(api_client: APIClient) -> None:
    response = api_client.get(reverse("health:ready"))

    assert response.status_code == 200
    assert response.json() == {
        "database": "ok",
        "service": "microcrd-api",
        "status": "ok",
    }


@pytest.mark.django_db
def test_ready_health_reports_database_failure(api_client: APIClient) -> None:
    with patch("apps.core.views.connection.cursor", side_effect=DatabaseError):
        response = api_client.get(reverse("health:ready"))

    assert response.status_code == 503
    assert response.json() == {
        "database": "unavailable",
        "service": "microcrd-api",
        "status": "error",
    }
