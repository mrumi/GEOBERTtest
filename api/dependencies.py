# ============================================================
# api/dependencies.py — Shared FastAPI Dependencies
# ============================================================

import uuid

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import decode_access_token
from core.config import settings, Settings
from core.clients import AppClients
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token : str = Depends(oauth2_scheme),
    db    : AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT from the Authorization header and load the
    corresponding user. Every non-auth route depends on this,
    which is what enforces per-user data isolation — a session/
    message query filtered by this user's id can never return
    another user's data.
    """
    credentials_error = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Could not validate credentials",
        headers     = {"WWW-Authenticate": "Bearer"},
    )

    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise credentials_error

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_error

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_error

    return user


def get_clients(request: Request) -> AppClients:
    """
    Retrieve the singleton AppClients (models/qdrant/groq) that
    was loaded once at startup — see main.py's lifespan hook.
    Never re-created per request.
    """
    return request.app.state.clients


def get_organism_resolver(request: Request):
    """Retrieve the singleton OrganismResolver loaded at startup."""
    return request.app.state.organism_resolver


def get_settings() -> Settings:
    return settings