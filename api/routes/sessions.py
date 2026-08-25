# ============================================================
# api/routes/sessions.py — Session History
# ============================================================
# Backs the "Session History"
# panel from the frontend mockup: list, view, and create sessions.
# ============================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from api.dependencies import get_current_user
from models.user import User
from models.session import ChatSession
from api.schemas import SessionSummary, SessionDetail

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    db          : AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sessions belonging to the current user, most recent first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=SessionSummary, status_code=201)
async def create_session(
    db          : AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Explicit "New Session" — starts a fresh thread with no
    carried-over context. (POST /query with session_id=None
    also implicitly creates a session, so this endpoint is for
    the frontend's "New Session" button specifically, before
    the user has typed a query yet.)
    """
    session = ChatSession(user_id=current_user.id, title="New session")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id  : uuid.UUID,
    db          : AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch one session with its full message history.
    Scoped to current_user — requesting another user's session_id
    returns 404, not 403, to avoid confirming the ID exists at all.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id  : uuid.UUID,
    db          : AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a session and all its messages (cascades via
    models/message.py's ondelete=CASCADE foreign key).
    Scoped to current_user — same 404-not-403 reasoning as
    get_session() above.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()