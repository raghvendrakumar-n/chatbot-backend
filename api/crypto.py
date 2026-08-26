"""Encrypt / decrypt secrets stored in the database (Fernet).

Uses a key derived from Django ``SECRET_KEY`` so values are not stored in
plaintext. Changing ``SECRET_KEY`` will invalidate previously encrypted rows.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    value = (plain or "").strip()
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    value = (cipher or "").strip()
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""
