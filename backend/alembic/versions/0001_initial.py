"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-24 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

from app.db.base import Base
from app import models

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
