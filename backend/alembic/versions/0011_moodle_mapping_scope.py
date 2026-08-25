from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0011_moodle_mapping_scope"
down_revision: str | None = "0010_moodle_submissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "moodle_submissions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("moodle_submissions")}
    if "moodle_group_id" not in columns:
        op.add_column("moodle_submissions", sa.Column("moodle_group_id", sa.String(length=255), nullable=True))
        op.create_index("ix_moodle_submissions_moodle_group_id", "moodle_submissions", ["moodle_group_id"])
    if "moodle_group_name" not in columns:
        op.add_column("moodle_submissions", sa.Column("moodle_group_name", sa.String(length=255), nullable=True))
    if "methodist_email" not in columns:
        op.add_column("moodle_submissions", sa.Column("methodist_email", sa.String(length=255), nullable=True))
        op.create_index("ix_moodle_submissions_methodist_email", "moodle_submissions", ["methodist_email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "moodle_submissions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("moodle_submissions")}
    indexes = {index["name"] for index in inspector.get_indexes("moodle_submissions")}
    if "ix_moodle_submissions_methodist_email" in indexes:
        op.drop_index("ix_moodle_submissions_methodist_email", table_name="moodle_submissions")
    if "methodist_email" in columns:
        op.drop_column("moodle_submissions", "methodist_email")
    if "moodle_group_name" in columns:
        op.drop_column("moodle_submissions", "moodle_group_name")
    if "ix_moodle_submissions_moodle_group_id" in indexes:
        op.drop_index("ix_moodle_submissions_moodle_group_id", table_name="moodle_submissions")
    if "moodle_group_id" in columns:
        op.drop_column("moodle_submissions", "moodle_group_id")
