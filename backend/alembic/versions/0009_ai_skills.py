from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_ai_skills"
down_revision: str | None = "0008_add_local_ai_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_skills" in inspector.get_table_names():
        return
    op.create_table(
        "ai_skills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_skills_owner_id", "ai_skills", ["owner_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_skills" in inspector.get_table_names():
        op.drop_index("ix_ai_skills_owner_id", table_name="ai_skills")
        op.drop_table("ai_skills")
