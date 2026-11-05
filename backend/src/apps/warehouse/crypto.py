from __future__ import annotations

import base64
import hashlib
import unicodedata
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

ENCRYPTED_VALUE_PREFIX = "enc:v1:"


def _derive_fernet_key(secret: str) -> bytes:
    material = f"microcrd:warehouse:pii:v1:{secret}".encode()
    return base64.urlsafe_b64encode(hashlib.sha256(material).digest())


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    configured_keys = settings.WAREHOUSE_PII_ENCRYPTION_KEYS
    if isinstance(configured_keys, str):
        configured_keys = [configured_keys]
    keys = [str(key) for key in configured_keys if str(key)]
    if not keys:
        raise ImproperlyConfigured("At least one warehouse PII encryption key is required.")
    return MultiFernet([Fernet(_derive_fernet_key(key)) for key in keys])


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    if value.startswith(ENCRYPTED_VALUE_PREFIX):
        return value
    token = _fernet().encrypt(value.encode()).decode()
    return f"{ENCRYPTED_VALUE_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(ENCRYPTED_VALUE_PREFIX):
        raise ValidationError("Warehouse PII must be stored as authenticated ciphertext.")
    try:
        return _fernet().decrypt(value.removeprefix(ENCRYPTED_VALUE_PREFIX).encode()).decode()
    except InvalidToken as exc:
        raise ValidationError("Encrypted warehouse value could not be authenticated.") from exc


def normalize_match_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold().strip()
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return "".join(character for character in normalized if character.isalnum())
