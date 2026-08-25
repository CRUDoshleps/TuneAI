from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_ai_provider_configs"
down_revision: str | None = "0006_demo_roles_rag_competencies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name == "postgresql":
        sa.Enum("mock", "yandex", "openai_compatible", name="aiproviderenum").create(bind, checkfirst=True)
    if "ai_provider_configs" in inspector.get_table_names():
        return
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    provider_type = (
        postgresql.ENUM(
            "mock",
            "yandex",
            "openai_compatible",
            name="aiproviderenum",
            create_type=False,
        )
        if bind.dialect.name == "postgresql"
        else sa.String(length=32)
    )
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", provider_type, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credentials", json_type, nullable=False, server_default="{}"),
        sa.Column("config", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_provider_configs_is_active", "ai_provider_configs", ["is_active"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_provider_configs" in inspector.get_table_names():
        op.drop_index("ix_ai_provider_configs_is_active", table_name="ai_provider_configs")
        op.drop_table("ai_provider_configs")
    if bind.dialect.name == "postgresql":
        sa.Enum("mock", "yandex", "openai_compatible", name="aiproviderenum").drop(bind, checkfirst=True)
