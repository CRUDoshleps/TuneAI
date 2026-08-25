from collections.abc import Sequence

from alembic import op


revision: str = "0008_add_local_ai_provider"
down_revision: str | None = "0007_ai_provider_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE aiproviderenum ADD VALUE IF NOT EXISTS 'local'")


def downgrade() -> None:
    pass
