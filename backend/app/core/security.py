from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


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
