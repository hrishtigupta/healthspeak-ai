"""Password hashing (Argon2id) and session-token helpers."""

import hashlib
import re
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi's defaults are Argon2id with RFC 9106 "low memory" parameters.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check, so unknown accounts are not faster to reject."""
    verify_password(_dummy_hash(), password)


def new_session_token() -> str:
    """A 256-bit random token. Only its hash is ever stored in the database."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_PHONE_STRIP = re.compile(r"[\s\-().]")


def normalize_phone(raw: str, default_country_code: str = "91") -> str | None:
    """Normalise to +<digits>. A bare 10-digit number gets the default country code.

    Returns None if the result is not 8-15 digits (E.164 length).
    """
    s = _PHONE_STRIP.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+"):
        digits = s[1:]
    else:
        digits = s
        if len(digits) == 10:
            digits = default_country_code + digits
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        return None
    return "+" + digits


def normalize_email(raw: str) -> str:
    return raw.strip().lower()
