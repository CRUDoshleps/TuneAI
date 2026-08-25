"""answer text and rag scope

Revision ID: 0005_answer_text_and_rag_scope
Revises: 0004_add_material_question_scope
Create Date: 2026-07-30 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_answer_text_and_rag_scope"
down_revision: str | None = "0004_add_material_question_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'methodist'")
        answer_type = sa.Enum("audio", "text", name="answertypeenum")
        answer_type.create(bind, checkfirst=True)

    answer_columns = {column["name"] for column in inspector.get_columns("answers")}
    if "answer_type" not in answer_columns:
        op.add_column(
            "answers",
            sa.Column(
                "answer_type",
                sa.Enum("audio", "text", name="answertypeenum") if bind.dialect.name == "postgresql" else sa.String(length=16),
                nullable=False,
                server_default="audio",
            ),
        )
    if "text_response" not in answer_columns:
        op.add_column("answers", sa.Column("text_response", sa.Text(), nullable=True))
    if "idempotency_key" not in answer_columns:
        op.add_column("answers", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        op.create_index("ix_answers_idempotency_key", "answers", ["idempotency_key"], unique=False)

    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("answers")}
    if "uq_answer_attempt_question" not in unique_constraints:
        op.create_unique_constraint("uq_answer_attempt_question", "answers", ["attempt_id", "question_id"])

    chunk_columns = {column["name"] for column in inspector.get_columns("material_chunks")}
    if "question_id" not in chunk_columns:
        op.add_column("material_chunks", sa.Column("question_id", sa.String(length=36), nullable=True))
        op.create_index("ix_material_chunks_question_id", "material_chunks", ["question_id"], unique=False)
        op.create_foreign_key(
            "fk_material_chunks_question_id_questions",
            "material_chunks",
            "questions",
            ["question_id"],
            ["id"],
        )
        if bind.dialect.name == "postgresql":
            op.execute(
                "UPDATE material_chunks SET question_id = materials.question_id "
                "FROM materials WHERE material_chunks.material_id = materials.id"
            )
        else:
            op.execute(
                "UPDATE material_chunks SET question_id = ("
                "SELECT materials.question_id FROM materials WHERE material_chunks.material_id = materials.id"
                ")"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    chunk_columns = {column["name"] for column in inspector.get_columns("material_chunks")}
    if "question_id" in chunk_columns:
        foreign_key = next(
            (
                item
                for item in inspector.get_foreign_keys("material_chunks")
                if item.get("constrained_columns") == ["question_id"]
            ),
            None,
        )
        if foreign_key and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], "material_chunks", type_="foreignkey")
        op.drop_index("ix_material_chunks_question_id", table_name="material_chunks")
        op.drop_column("material_chunks", "question_id")

    answer_columns = {column["name"] for column in inspector.get_columns("answers")}
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("answers")}
    if "uq_answer_attempt_question" in unique_constraints:
        op.drop_constraint("uq_answer_attempt_question", "answers", type_="unique")
    if "idempotency_key" in answer_columns:
        op.drop_index("ix_answers_idempotency_key", table_name="answers")
        op.drop_column("answers", "idempotency_key")
    if "text_response" in answer_columns:
        op.drop_column("answers", "text_response")
    if "answer_type" in answer_columns:
        op.drop_column("answers", "answer_type")
    if bind.dialect.name == "postgresql":
        sa.Enum("audio", "text", name="answertypeenum").drop(bind, checkfirst=True)
