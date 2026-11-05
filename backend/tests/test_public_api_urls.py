from django.urls import reverse
from rest_framework.test import APIClient


def test_public_api_reverse_names_use_cutover_paths() -> None:
    assert reverse("imports:import-batch-list") == "/api/import-batches/"
    assert reverse("imports:import-batch-issues", kwargs={"pk": "batch-id"}) == (
        "/api/import-batches/batch-id/issues/"
    )
    assert reverse("applications:credit-request-list") == "/api/credit-requests/"
    assert reverse("applications:credit-request-detail", kwargs={"pk": "request-id"}) == (
        "/api/credit-requests/request-id/"
    )
    assert reverse("analytics:metadata") == "/api/dashboard/metadata/"
    assert reverse("assistant:messages") == "/api/assistant/messages/"
    assert reverse("warehouse:reference-data") == "/api/reference-data/"
    assert reverse("warehouse:reference-agencies") == "/api/reference-data/agencies/"
    assert reverse("warehouse:reference-employees") == "/api/reference-data/employees/"
    assert reverse(
        "warehouse:reference-agency", kwargs={"pk": "00000000-0000-0000-0000-000000000000"}
    ) == ("/api/reference-data/agencies/00000000-0000-0000-0000-000000000000/")


def test_legacy_api_prefixes_are_not_exposed() -> None:
    client = APIClient()

    assert client.get("/api/imports/").status_code == 404
    assert client.get("/api/applications/").status_code == 404
    assert client.get("/api/analytics/overview/").status_code == 404
    assert client.get("/api/dashboard/geography/").status_code == 404
    assert client.get("/api/alerts/").status_code == 404
