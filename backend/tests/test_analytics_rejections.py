from decimal import Decimal

from apps.analytics import services


def test_rejections_exposes_a_single_controlled_reason(monkeypatch: object) -> None:
    row = {
        "agency_id": "agency-1",
        "agency__name": "ARIANA",
        "gp_id": "gp-1",
        "gp__name": "Inconnu",
        "rejection_reason__name": "Dossier incomplet",
        "is_rejected": True,
        "requested_amount": Decimal("1000"),
        "current_tb1_row__batch__status": "completed",
        "current_tb2_row__batch__status": "completed",
    }
    monkeypatch.setattr(services, "_fact_rows", lambda _filters: [row])  # type: ignore[attr-defined]

    results, suppressed_groups = services.rejections(filters=None)  # type: ignore[arg-type]

    assert suppressed_groups == 0
    assert results[0]["reason_label"] == "Dossier incomplet"
    assert results[0]["rejected_requests"] == 1
