from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.permissions import has_active_user


class ApplicationReadPermission(BasePermission):
    """Authorize current warehouse facts without granting import-table access."""

    def has_permission(self, request: Request, _view: APIView) -> bool:
        if request.method not in SAFE_METHODS or not request.user.is_authenticated:
            return False
        return has_active_user(request.user)

    def has_object_permission(self, request: Request, _view: APIView, _obj: object) -> bool:
        return has_active_user(request.user)
