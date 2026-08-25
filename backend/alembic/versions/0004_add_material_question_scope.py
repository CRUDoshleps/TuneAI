"""add material question scope

Revision ID: 0004_add_material_question_scope
Revises: 0003_add_answer_review
Create Date: 2026-07-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_add_material_question_scope"
down_revision: str | None = "0003_add_answer_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("materials")}
    if "question_id" not in columns:
        op.add_column("materials", sa.Column("question_id", sa.String(length=36), nullable=True))

    foreign_keys = inspector.get_foreign_keys("materials")
    has_question_foreign_key = any(
        foreign_key.get("constrained_columns") == ["question_id"]
        and foreign_key.get("referred_table") == "questions"
        and foreign_key.get("referred_columns") == ["id"]
        for foreign_key in foreign_keys
    )
    if not has_question_foreign_key:
        op.create_foreign_key(
            "fk_materials_question_id_questions",
            "materials",
            "questions",
            ["question_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    question_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("materials")
            if foreign_key.get("constrained_columns") == ["question_id"]
            and foreign_key.get("referred_table") == "questions"
            and foreign_key.get("referred_columns") == ["id"]
        ),
        None,
    )
    if question_foreign_key and question_foreign_key.get("name"):
        op.drop_constraint(question_foreign_key["name"], "materials", type_="foreignkey")

    columns = {column["name"] for column in inspector.get_columns("materials")}
    if "question_id" in columns:
        op.drop_column("materials", "question_id")
