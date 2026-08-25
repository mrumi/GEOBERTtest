# ============================================================
# models/session.py — Chat Session (Thread) ORM Model
# ============================================================
# Named "ChatSession" (not "Session") to avoid confusion with
# SQLAlchemy's own Session class used throughout core/database.py.
# multi-turn — a session can hold many
# messages (follow-up queries keep prior filters/context until
# the user explicitly starts "New Session").
# ============================================================

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Short human-readable label for the session list UI
    # (e.g. truncated first query, or an LLM-generated title later).
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New session")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user     = relationship("User", back_populates="sessions")
    messages = relationship(
        "Message",
        back_populates = "session",
        cascade        = "all, delete-orphan",
        order_by       = "Message.created_at",
    )