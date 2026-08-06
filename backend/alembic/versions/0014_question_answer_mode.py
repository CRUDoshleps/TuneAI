from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0014_question_answer_mode"
down_revision: str | None = "0013_assessment_builder_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("questions")}
    if bind.dialect.name == "postgresql":
        answer_mode = sa.Enum("audio", "text", "both", name="questionanswermodeenum")
        answer_mode.create(bind, checkfirst=True)
        column_type = answer_mode
    else:
        column_type = sa.String(length=16)
    if "answer_mode" not in columns:
        op.add_column("questions", sa.Column("answer_mode", column_type, nullable=False, server_default="both"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("questions")}
    if "answer_mode" in columns:
        op.drop_column("questions", "answer_mode")
    if bind.dialect.name == "postgresql":
        sa.Enum("audio", "text", "both", name="questionanswermodeenum").drop(bind, checkfirst=True)
