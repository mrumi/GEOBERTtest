# ============================================================
# api/routes/auth.py — Registration, Login, Email Verification,
# Password Reset, Current User
# ============================================================
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update

from core.config import settings
from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from core.email_service import send_verification_email, send_password_reset_email
from models.user import User
from models.email_token import EmailToken
from api.dependencies import get_current_user
from api.schemas import (
    UserRegister, UserLogin, TokenResponse, UserOut,
    RegisterResponse, EmailRequest, TokenConfirm, ResetPasswordRequest, MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

PURPOSE_VERIFY = "verify_email"
PURPOSE_RESET  = "reset_password"


# ── Token helpers ────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _recently_issued(db: AsyncSession, user_id: UUID, purpose: str) -> bool:
    """True if a token for this user+purpose was created within the cooldown
    window — stops the resend/forgot endpoints being used to spam an inbox."""
    cutoff = _now() - timedelta(seconds=settings.EMAIL_RESEND_COOLDOWN_SECONDS)
    result = await db.execute(
        select(EmailToken.id)
        .where(EmailToken.user_id == user_id, EmailToken.purpose == purpose, EmailToken.created_at >= cutoff)
        .limit(1)
    )
    return result.first() is not None


async def _issue_token(db: AsyncSession, user_id: UUID, purpose: str, ttl: timedelta) -> str:
    """Create a fresh token (superseding any unused older ones) and return the raw value."""
    await db.execute(
        update(EmailToken)
        .where(EmailToken.user_id == user_id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None))
        .values(used_at=_now())
    )
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(user_id=user_id, purpose=purpose, token_hash=_hash_token(raw), expires_at=_now() + ttl))
    await db.commit()
    return raw


async def _consume_token(db: AsyncSession, raw: str, purpose: str) -> User | None:
    """Validate a raw token, mark it used, and return its user (caller commits)."""
    result = await db.execute(
        select(EmailToken).where(
            EmailToken.token_hash == _hash_token(raw),
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > _now(),
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        return None
    token.used_at = _now()
    return await db.get(User, token.user_id)


# ── Endpoints ────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):

    existing = await db.execute(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    existing_user = existing.scalar_one_or_none()

    if existing_user is not None:
        if existing_user.email == payload.email:
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        full_name       = payload.full_name,
        username        = payload.username,
        email           = payload.email,
        hashed_password = hash_password(payload.password),
        role            = payload.role,
        is_verified     = False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Capture plain values now — commits expire ORM attributes, and
    # touching them afterwards in async code raises MissingGreenlet.
    user_id, email, full_name = user.id, user.email, user.full_name

    raw = await _issue_token(db, user_id, PURPOSE_VERIFY, timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS))
    background_tasks.add_task(send_verification_email, email, full_name, raw)

    return RegisterResponse(message="Account created. Check your email to verify your address.", email=email)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    # Checked after the password so only the account owner learns verification state.
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before signing in.")

    token = create_access_token(user_id=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: TokenConfirm, db: AsyncSession = Depends(get_db)):
    user = await _consume_token(db, payload.token, PURPOSE_VERIFY)
    if user is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    user.is_verified = True
    await db.commit()
    return MessageResponse(message="Email verified. You can now sign in.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(payload: EmailRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    generic = MessageResponse(message="If that account exists and is unverified, a new verification email is on its way.")

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or user.is_verified:
        return generic

    user_id, email, full_name = user.id, user.email, user.full_name
    if await _recently_issued(db, user_id, PURPOSE_VERIFY):
        return generic

    raw = await _issue_token(db, user_id, PURPOSE_VERIFY, timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS))
    background_tasks.add_task(send_verification_email, email, full_name, raw)
    return generic


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: EmailRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # Same response whether or not the email exists, so this can't be
    # used to discover which addresses have accounts.
    generic = MessageResponse(message="If that email has an account, a password reset link is on its way.")

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        return generic

    user_id, email, full_name = user.id, user.email, user.full_name
    if await _recently_issued(db, user_id, PURPOSE_RESET):
        return generic

    raw = await _issue_token(db, user_id, PURPOSE_RESET, timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES))
    background_tasks.add_task(send_password_reset_email, email, full_name, raw)
    return generic


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await _consume_token(db, payload.token, PURPOSE_RESET)
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user.hashed_password = hash_password(payload.new_password)
    user.is_verified = True   # they just proved control of the inbox
    await db.commit()
    return MessageResponse(message="Password updated. You can now sign in.")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the logged-in user's profile — used by the frontend to show name/role in the header."""
    return current_user