"""Auth stabilization — idempotent column migration.

Revision ID: 009
Revises: 008
Create Date: 2026-06-01

Ensures users table has all required columns regardless of prior migration state.
Checks existence before adding to avoid errors on re-run.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def upgrade() -> None:
    # Ensure all columns required by the User model exist
    if not _column_exists("users", "failed_login_attempts"):
        op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), server_default="0"))

    if not _column_exists("users", "locked_until"):
        op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))

    if not _column_exists("users", "deleted_at"):
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # Expand role column if needed (migration 004 used String(20), model uses String(32))
    try:
        op.alter_column("users", "role", type_=sa.String(32), existing_type=sa.String(20), nullable=False, server_default="User")
    except Exception:
        pass


def downgrade() -> None:
    pass
