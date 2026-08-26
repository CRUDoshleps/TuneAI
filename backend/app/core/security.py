from datetime import datetime, timedelta, timezone
import hashlib
from typing import Literal

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings


PASSWORD_HASH_PREFIX = "$tuneai-bcrypt-sha256$"
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode("utf-8")
        if hashed_password.startswith(PASSWORD_HASH_PREFIX):
            password_bytes = hashlib.sha256(password_bytes).digest()
            bcrypt_hash = hashed_password.removeprefix(PASSWORD_HASH_PREFIX)
        else:
            # Legacy Passlib hashes used raw bcrypt and silently ignored bytes
            # after bcrypt's 72-byte limit. Keep those accounts readable while
            # all newly written hashes use the unambiguous pre-hashed format.
            password_bytes = password_bytes[:72]
            bcrypt_hash = hashed_password
        return bcrypt.checkpw(password_bytes, bcrypt_hash.encode("ascii"))
    except (TypeError, UnicodeError, ValueError):
        return False


def hash_password(password: str) -> str:
    password_digest = hashlib.sha256(password.encode("utf-8")).digest()
    bcrypt_hash = bcrypt.hashpw(password_digest, bcrypt.gensalt()).decode("ascii")
    return f"{PASSWORD_HASH_PREFIX}{bcrypt_hash}"


def create_token(subject: str, token_type: Literal["access", "refresh"], minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if token_type == "refresh":
        expire = now + timedelta(days=settings.refresh_token_expire_days)
    else:
        expire = now + timedelta(minutes=minutes or settings.access_token_expire_minutes)
    payload = {"sub": subject, "type": token_type, "iat": int(now.timestamp()), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Invalid token type")
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token subject is missing")
    return str(subject)
