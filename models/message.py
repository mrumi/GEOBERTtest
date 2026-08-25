# ============================================================
# models/message.py — Message (One Turn) ORM Model
# ============================================================
# One row per turn: either the user's query (role="user") or
# the generated answer (role="assistant"). The JSONB columns
# store already produces —
# query_info, dropped_filters, top_gse_ids — so a session's
# prior turns can be reloaded and fed back into
# analyze_query()'s session_memory parameter for multi-turn
# follow-up handling (see rag/query_understanding.py notes).
# ============================================================

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "user" or "assistant"
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # For role="user": the raw query text.
    # For role="assistant": the generated answer text.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Only populated for role="assistant" messages — mirrors
    # rag_node()'s return dict fields directly.
    query_info      : Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dropped_filters : Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    top_gse_ids     : Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Result snapshot for this turn (per-query result restoration). Only populated for role="assistant" messages;
    # what this turn returned, without re-running the query.
    studies         : Mapped[list | None] = mapped_column(JSONB, nullable=True)
    samples         : Mapped[list | None] = mapped_column(JSONB, nullable=True)
    dashboard_stats : Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")