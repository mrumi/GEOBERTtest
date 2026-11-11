"""reset password

Revision ID: c2459d288ce4
Revises: f01d3e76d98d
Create Date: 2026-11-11 19:41:53.775402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c2459d288ce4'
down_revision: Union[str, Sequence[str], None] = 'f01d3e76d98d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default=true marks every EXISTING user as verified (so nobody is
    # locked out), then the default flips to false for newly registered users.
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("users", "is_verified", server_default=sa.false())

    op.create_table(
        "email_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
    op.create_index("ix_email_tokens_token_hash", "email_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_email_tokens_token_hash", table_name="email_tokens")
    op.drop_index("ix_email_tokens_user_id", table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_column("users", "is_verified")