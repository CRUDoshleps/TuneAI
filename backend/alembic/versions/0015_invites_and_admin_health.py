from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0015_invites_and_admin_health"
down_revision: str | None = "0014_question_answer_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "must_change_password" not in user_columns:
        op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    tables = set(inspector.get_table_names())
    if "user_invites" not in tables:
        op.create_table(
            "user_invites",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("created_by_id", sa.String(length=36), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_user_invite_token_hash"),
        )
        op.create_index("ix_user_invites_email", "user_invites", ["email"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_invites" in set(inspector.get_table_names()):
        op.drop_index("ix_user_invites_email", table_name="user_invites")
        op.drop_table("user_invites")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "must_change_password" in user_columns:
        op.drop_column("users", "must_change_password")
