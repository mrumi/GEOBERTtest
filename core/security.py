# ============================================================
# core/security.py — Password Hashing & JWT Tokens
# ============================================================
# Supports the multi-user
# authentication flow on: email/password login,
# JWT bearer token on every subsequent request.
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage (users.hashed_password)."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a login attempt's password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT for a logged-in user.

    Args:
        user_id: The user's database ID (stored as the "sub" claim).

    Returns:
        Encoded JWT string, to be returned to the client on
        login/register and sent back as "Authorization: Bearer <token>"
        on every subsequent request.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    Verify and decode a JWT.

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        The user_id ("sub" claim) if the token is valid and not
        expired, or None if verification fails for any reason
        (expired, tampered, malformed).
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None