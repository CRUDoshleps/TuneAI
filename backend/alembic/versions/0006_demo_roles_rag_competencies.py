from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_demo_roles_rag_competencies"
down_revision: str | None = "0005_answer_text_and_rag_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        sa.Enum("pending", "indexed", "failed", name="materialindexstatusenum").create(bind, checkfirst=True)

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_demo" not in user_columns:
        op.add_column("users", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "expires_at" not in user_columns:
        op.add_column("users", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    if "created_by_id" not in user_columns:
        op.add_column("users", sa.Column("created_by_id", sa.String(length=36), nullable=True))
        op.create_foreign_key("fk_users_created_by_id_users", "users", "users", ["created_by_id"], ["id"])

    test_columns = {column["name"] for column in inspector.get_columns("tests")}
    if "is_demo" not in test_columns:
        op.add_column("tests", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "expires_at" not in test_columns:
        op.add_column("tests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    if "competencies" not in question_columns:
        column_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
        op.add_column("questions", sa.Column("competencies", column_type, nullable=False, server_default="[]"))

    material_columns = {column["name"] for column in inspector.get_columns("materials")}
    if "index_status" not in material_columns:
        op.add_column(
            "materials",
            sa.Column(
                "index_status",
                sa.Enum("pending", "indexed", "failed", name="materialindexstatusenum") if bind.dialect.name == "postgresql" else sa.String(length=32),
                nullable=False,
                server_default="indexed",
            ),
        )
    if "index_error" not in material_columns:
        op.add_column("materials", sa.Column("index_error", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    material_columns = {column["name"] for column in inspector.get_columns("materials")}
    if "index_error" in material_columns:
        op.drop_column("materials", "index_error")
    if "index_status" in material_columns:
        op.drop_column("materials", "index_status")

    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    if "competencies" in question_columns:
        op.drop_column("questions", "competencies")

    test_columns = {column["name"] for column in inspector.get_columns("tests")}
    if "expires_at" in test_columns:
        op.drop_column("tests", "expires_at")
    if "is_demo" in test_columns:
        op.drop_column("tests", "is_demo")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "created_by_id" in user_columns:
        foreign_key = next(
            (
                item
                for item in inspector.get_foreign_keys("users")
                if item.get("constrained_columns") == ["created_by_id"]
            ),
            None,
        )
        if foreign_key and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], "users", type_="foreignkey")
        op.drop_column("users", "created_by_id")
    if "expires_at" in user_columns:
        op.drop_column("users", "expires_at")
    if "is_demo" in user_columns:
        op.drop_column("users", "is_demo")

    if bind.dialect.name == "postgresql":
        sa.Enum("pending", "indexed", "failed", name="materialindexstatusenum").drop(bind, checkfirst=True)
