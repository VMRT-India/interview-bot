import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings

_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores bytes beyond this — reject longer passwords

# Domains known to ignore dots in the local-part (Gmail-specific — most providers do NOT
# do this, e.g. Outlook/Yahoo treat "j.doe@" and "jdoe@" as genuinely different mailboxes).
_DOT_INSENSITIVE_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(email: str) -> str:
    """Canonicalizes an email for uniqueness checks, closing common alias tricks used to
    register multiple accounts against one real inbox:
      - case: `Foo@Gmail.com` -> `foo@gmail.com`
      - plus-addressing: `foo+anything@gmail.com` -> `foo@gmail.com` (applied to all
        domains — near-universally supported, and harmless even where unsupported since
        such an address wouldn't resolve to a distinct real mailbox anyway)
      - dot-insensitivity: `f.o.o@gmail.com` -> `foo@gmail.com` (Gmail/Googlemail only)

    Non-email input (e.g. a phone number used as a login identifier) is returned unchanged.
    """
    email = email.strip().lower()
    if "@" not in email:
        return email

    local, _, domain = email.rpartition("@")
    local = local.split("+", 1)[0]
    if domain in _DOT_INSENSITIVE_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"


def hash_password(password: str) -> str:
    if len(password.encode()) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"password must be at most {_BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Raises jwt.PyJWTError (expired/invalid/malformed) — caller translates to 401."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return uuid.UUID(payload["sub"])
