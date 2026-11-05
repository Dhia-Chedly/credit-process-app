from __future__ import annotations

from contextlib import suppress
from typing import Any, Literal, cast

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.authentication import (
    issue_token_pair,
    token_auth_version,
)
from apps.accounts.models import User
from apps.accounts.serializers import (
    AuthTokenResponseSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    RegisterSerializer,
)


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    same_site = cast(Literal["Lax", "Strict", "None", False], settings.JWT_REFRESH_COOKIE_SAMESITE)
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        samesite=same_site,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    same_site = cast(Literal["Lax", "Strict", "None", False], settings.JWT_REFRESH_COOKIE_SAMESITE)
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=same_site,
    )


def _token_response(access: str, refresh: str) -> Response:
    response = Response(
        {
            "access": access,
            "access_expires_in": int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        }
    )
    response["Cache-Control"] = "no-store"
    _set_refresh_cookie(response, refresh)
    return response


class LoginRateThrottle(SimpleRateThrottle):
    scope = "auth_login"

    def get_cache_key(self, request: Request, _view: APIView) -> str:
        username = str(request.data.get("username", "")).strip().casefold()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{self.get_ident(request)}:{username}",
        }


class RegisterRateThrottle(LoginRateThrottle):
    scope = "auth_register"


class RegisterView(APIView):
    authentication_classes: list[type[Any]] = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    @extend_schema(request=RegisterSerializer, responses={201: AuthTokenResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=serializer.validated_data["username"],
                    password=serializer.validated_data["password"],
                )
        except IntegrityError:
            return Response(
                {"username": ["This username is already in use."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        access, refresh = issue_token_pair(user)
        response = _token_response(access, refresh)
        response.status_code = status.HTTP_201_CREATED
        return response


class LoginView(APIView):
    authentication_classes: list[type[Any]] = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(request=LoginSerializer, responses={200: AuthTokenResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not isinstance(user, User) or not user.is_active:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        access, refresh = issue_token_pair(user)
        return _token_response(access, refresh)


class RefreshView(APIView):
    authentication_classes: list[type[Any]] = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: AuthTokenResponseSerializer})
    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            return Response({"detail": "Refresh token required."}, status=401)
        try:
            old_refresh = RefreshToken(cast(Any, raw_refresh))
            user = User.objects.get(pk=old_refresh["user_id"])
            if not user.is_active or token_auth_version(old_refresh) != user.auth_version:
                raise TokenError("Session revoked")
            old_refresh.blacklist()
            access, refresh = issue_token_pair(user)
        except (KeyError, TokenError, User.DoesNotExist):
            response = Response({"detail": "Invalid or expired refresh token."}, status=401)
            _clear_refresh_cookie(response)
            return response
        return _token_response(access, refresh)


class LogoutView(APIView):
    authentication_classes: list[type[Any]] = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh:
            with suppress(TokenError):
                RefreshToken(cast(Any, raw_refresh)).blacklist()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CurrentUserSerializer)
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(CurrentUserSerializer(user, context={"request": request}).data)
