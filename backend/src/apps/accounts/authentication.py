from typing import Any, cast

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import Token

from apps.accounts.models import User


class VersionedJWTAuthentication(JWTAuthentication):
    """Reject tokens issued before a governed account security change."""

    def get_user(self, validated_token: Token) -> Any:
        user = cast(User, super().get_user(validated_token))
        token_version = validated_token.get("auth_version")
        if token_version != user.auth_version:
            raise AuthenticationFailed("This session has been revoked.", code="session_revoked")
        if not user.is_active:
            raise AuthenticationFailed("This account is inactive.", code="account_inactive")
        return user


def issue_token_pair(user: User) -> tuple[str, str]:
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    refresh["auth_version"] = user.auth_version
    return str(refresh.access_token), str(refresh)


def token_auth_version(token: Any) -> int | None:
    value = token.get("auth_version")
    return value if isinstance(value, int) else None


class VersionedJWTAuthenticationScheme(  # type: ignore[no-untyped-call]
    OpenApiAuthenticationExtension
):
    target_class = "apps.accounts.authentication.VersionedJWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        _ = auto_schema
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
