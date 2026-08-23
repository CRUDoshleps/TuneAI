from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0016_mixed_questions_imports_audit"
down_revision: str | None = "0015_invites_and_admin_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE answertypeenum ADD VALUE IF NOT EXISTS 'choice'")
    inspector = sa.inspect(bind)
    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    for name, column in (
        ("question_type", sa.Column("question_type", sa.String(length=32), nullable=False, server_default="open_response")),
        ("options", sa.Column("options", sa.JSON(), nullable=False, server_default="[]")),
        ("correct_option_ids", sa.Column("correct_option_ids", sa.JSON(), nullable=False, server_default="[]")),
        ("explanation", sa.Column("explanation", sa.Text(), nullable=False, server_default="")),
        ("source_refs", sa.Column("source_refs", sa.JSON(), nullable=False, server_default="[]")),
    ):
        if name not in question_columns:
            op.add_column("questions", column)

    answer_columns = {column["name"] for column in inspector.get_columns("answers")}
    if "selected_option_ids" not in answer_columns:
        op.add_column("answers", sa.Column("selected_option_ids", sa.JSON(), nullable=False, server_default="[]"))

    tables = set(inspector.get_table_names())
    if "source_imports" not in tables:
        op.create_table(
            "source_imports",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("test_id", sa.String(length=36), nullable=False),
            sa.Column("owner_id", sa.String(length=36), nullable=False),
            sa.Column("source_filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=160), nullable=False),
            sa.Column("object_key", sa.String(length=1024), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("segments", sa.JSON(), nullable=False),
            sa.Column("excluded_segment_ids", sa.JSON(), nullable=False),
            sa.Column("generation_config", sa.JSON(), nullable=False),
            sa.Column("candidates", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_source_imports_test_id", "source_imports", ["test_id"])
        op.create_index("ix_source_imports_owner_id", "source_imports", ["owner_id"])
        op.create_index("ix_source_imports_status", "source_imports", ["status"])

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("entity_type", sa.String(length=80), nullable=False),
            sa.Column("entity_id", sa.String(length=120), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for name in ("actor_id", "action", "entity_type", "entity_id", "created_at"):
            op.create_index(f"ix_audit_logs_{name}", "audit_logs", [name])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "audit_logs" in tables:
        op.drop_table("audit_logs")
    if "source_imports" in tables:
        op.drop_table("source_imports")
    answer_columns = {column["name"] for column in inspector.get_columns("answers")}
    if "selected_option_ids" in answer_columns:
        op.drop_column("answers", "selected_option_ids")
    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    for name in ("source_refs", "explanation", "correct_option_ids", "options", "question_type"):
        if name in question_columns:
            op.drop_column("questions", name)
