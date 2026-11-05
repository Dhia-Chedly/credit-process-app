from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


def has_active_user(user: Any) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_active", False))


# Compatibility name for existing callers during the account simplification.
class ImportBatchPermission(BasePermission):
    def has_permission(self, request: Request, _view: APIView) -> bool:
        return has_active_user(request.user)

    def has_object_permission(self, request: Request, _view: APIView, _obj: Any) -> bool:
        return has_active_user(request.user)


class AnalyticsPermission(BasePermission):
    def has_permission(self, request: Request, _view: APIView) -> bool:
        return request.method in SAFE_METHODS and has_active_user(request.user)


class ReferenceDataPermission(BasePermission):
    """Allow only designated reference administrators to change governed values."""

    def has_permission(self, request: Request, _view: APIView) -> bool:
        return has_active_user(request.user) and bool(
            getattr(request.user, "is_reference_admin", False)
        )


def may_view_import_source_metadata(user: Any) -> bool:
    return has_active_user(user)


def capabilities_for_user(user: Any) -> dict[str, Any]:
    active = has_active_user(user)
    return {
        "can_import": active,
        "can_manage_reference_data": active and bool(getattr(user, "is_reference_admin", False)),
        "can_view_all_agencies": active,
        "can_view_client_pii": False,
        "can_approve_mappings": active,
        "credit_request_scope": "all" if active else "none",
    }
