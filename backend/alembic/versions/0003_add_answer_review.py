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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("answers")}

    additions = {
        "review_score": sa.Column("review_score", sa.Float(), nullable=True),
        "review_feedback": sa.Column("review_feedback", sa.Text(), nullable=True),
        "reviewed_by_id": sa.Column("reviewed_by_id", sa.String(length=36), nullable=True),
        "reviewed_at": sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("answers", column)

    foreign_keys = sa.inspect(bind).get_foreign_keys("answers")
    has_reviewed_by_foreign_key = any(
        foreign_key.get("constrained_columns") == ["reviewed_by_id"]
        and foreign_key.get("referred_table") == "users"
        and foreign_key.get("referred_columns") == ["id"]
        for foreign_key in foreign_keys
    )
    if not has_reviewed_by_foreign_key:
        op.create_foreign_key(
            "fk_answers_reviewed_by_id_users",
            "answers",
            "users",
            ["reviewed_by_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    reviewed_by_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("answers")
            if foreign_key.get("constrained_columns") == ["reviewed_by_id"]
            and foreign_key.get("referred_table") == "users"
            and foreign_key.get("referred_columns") == ["id"]
        ),
        None,
    )
    if reviewed_by_foreign_key and reviewed_by_foreign_key.get("name"):
        op.drop_constraint(reviewed_by_foreign_key["name"], "answers", type_="foreignkey")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("answers")}
    for name in ("reviewed_at", "reviewed_by_id", "review_feedback", "review_score"):
        if name in columns:
            op.drop_column("answers", name)
