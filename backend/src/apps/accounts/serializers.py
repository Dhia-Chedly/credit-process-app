from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User
from apps.core.permissions import capabilities_for_user


class CurrentUserSerializer(serializers.ModelSerializer[User]):
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "capabilities",
        )
        read_only_fields = fields

    def get_capabilities(self, obj: User) -> dict[str, Any]:
        return capabilities_for_user(obj)


class LoginSerializer(serializers.Serializer[dict[str, str]]):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class RegisterSerializer(serializers.Serializer[dict[str, str]]):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)
    password_confirmation = serializers.CharField(
        style={"input_type": "password"}, trim_whitespace=False
    )

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError({"password_confirmation": "Passwords do not match."})
        try:
            validate_password(attrs["password"], user=User(username=attrs["username"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class AuthTokenResponseSerializer(serializers.Serializer[dict[str, Any]]):
    access = serializers.CharField()
    access_expires_in = serializers.IntegerField()
