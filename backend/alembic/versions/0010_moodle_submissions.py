from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010_moodle_submissions"
down_revision: str | None = "0009_ai_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "moodle_submissions" in inspector.get_table_names():
        return
    op.create_table(
        "moodle_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_submission_id", sa.String(length=255), nullable=False),
        sa.Column("external_attempt_id", sa.String(length=255), nullable=True),
        sa.Column("moodle_user_id", sa.String(length=255), nullable=False),
        sa.Column("moodle_course_id", sa.String(length=255), nullable=True),
        sa.Column("moodle_activity_id", sa.String(length=255), nullable=True),
        sa.Column("test_id", sa.String(length=36), sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("question_id", sa.String(length=36), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("answer_id", sa.String(length=36), sa.ForeignKey("answers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("external_submission_id", name="uq_moodle_external_submission_id"),
    )
    op.create_index("ix_moodle_submissions_external_attempt_id", "moodle_submissions", ["external_attempt_id"])
    op.create_index("ix_moodle_submissions_moodle_user_id", "moodle_submissions", ["moodle_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "moodle_submissions" in inspector.get_table_names():
        op.drop_index("ix_moodle_submissions_moodle_user_id", table_name="moodle_submissions")
        op.drop_index("ix_moodle_submissions_external_attempt_id", table_name="moodle_submissions")
        op.drop_table("moodle_submissions")
