"""add examinee role

Revision ID: 0002_add_examinee_role
Revises: 0001_initial
Create Date: 2026-07-24 12:15:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0002_add_examinee_role"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'examinee'")


def downgrade() -> None:
    pass
