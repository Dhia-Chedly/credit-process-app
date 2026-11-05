from __future__ import annotations

from typing import Any, cast

from django.db import models

from apps.warehouse.crypto import ENCRYPTED_VALUE_PREFIX, decrypt_text, encrypt_text


class EncryptedTextField(models.TextField):  # type: ignore[type-arg]
    """A non-queryable text field encrypted with authenticated, rotatable keys."""

    description = "Authenticated encrypted text"

    def from_db_value(self, value: str | None, _expression: Any, _connection: Any) -> str:
        return decrypt_text(value or "")

    def to_python(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def get_prep_value(self, value: Any) -> str:
        prepared = cast(str | None, super().get_prep_value(value))
        if not prepared:
            return ""
        if prepared.startswith(ENCRYPTED_VALUE_PREFIX):
            return prepared
        return encrypt_text(prepared)
