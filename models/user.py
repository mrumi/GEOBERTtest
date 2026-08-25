# ============================================================
# models/user.py — User ORM Model
# ============================================================
# full_name, username, role added for the registration
# form (Name, Username, Email, Password, Role).
# ============================================================

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Plain string column (not a Postgres native enum) so new
    # roles can be added later without a schema migration — the
    # allowed set is validated at the API layer instead
    # (api/schemas.py's UserRole Literal type).
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="researcher")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")