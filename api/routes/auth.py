# ============================================================
# api/routes/auth.py — Registration, Login, Current User
# ============================================================
# Registration now collects full_name, username, role
# (in addition to email/password). Username must also be unique,
# checked alongside email. Added GET /auth/me so the frontend
# can display the logged-in user's name/role after login without
# re-parsing the JWT client-side.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from api.dependencies import get_current_user
from api.schemas import UserRegister, UserLogin, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):

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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user_id=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user_id=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the logged-in user's profile — used by the frontend to show name/role in the header."""
    return current_user