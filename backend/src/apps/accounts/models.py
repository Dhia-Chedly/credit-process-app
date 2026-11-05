from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


class UserManager(BaseUserManager["User"]):
    def create_user(self, username: str, password: str | None = None, **extra_fields: Any) -> User:
        if not username.strip():
            raise ValueError("A username is required.")
        user = self.model(username=username.strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, username: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_reference_admin", True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser):
    """The application's only account type: an active named operator."""

    last_login = None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128, db_column="password_hash")
    is_active = models.BooleanField(default=True)
    is_reference_admin = models.BooleanField(
        default=False,
        help_text="May manage governed operational reference data.",
    )
    auth_version = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: ClassVar[list[str]] = []
    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        db_table = '"auth"."users"'
        ordering = ["username"]

    @property
    def is_superuser(self) -> bool:
        return False

    @property
    def is_staff(self) -> bool:
        return False

    def clean(self) -> None:
        super().clean()
        if not self.username.strip():
            raise ValidationError({"username": "A username is required."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and not self._state.adding:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("password", "is_active", "auth_version")
                .first()
            )
            if (
                previous
                and (
                    previous["password"] != self.password or previous["is_active"] != self.is_active
                )
                and self.auth_version <= previous["auth_version"]
            ):
                self.auth_version = previous["auth_version"] + 1
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username
