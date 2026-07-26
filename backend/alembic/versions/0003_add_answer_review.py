"""add human answer review

Revision ID: 0003_add_answer_review
Revises: 0002_add_examinee_role
Create Date: 2026-07-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_add_answer_review"
down_revision: str | None = "0002_add_examinee_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("answers", sa.Column("review_score", sa.Float(), nullable=True))
    op.add_column("answers", sa.Column("review_feedback", sa.Text(), nullable=True))
    op.add_column("answers", sa.Column("reviewed_by_id", sa.String(length=36), nullable=True))
    op.add_column("answers", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_answers_reviewed_by_id_users",
        "answers",
        "users",
        ["reviewed_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_answers_reviewed_by_id_users", "answers", type_="foreignkey")
    op.drop_column("answers", "reviewed_at")
    op.drop_column("answers", "reviewed_by_id")
    op.drop_column("answers", "review_feedback")
    op.drop_column("answers", "review_score")
