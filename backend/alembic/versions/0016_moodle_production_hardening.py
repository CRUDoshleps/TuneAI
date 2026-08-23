from collections.abc import Sequence
from datetime import datetime, timezone
import os
import uuid

import sqlalchemy as sa
from alembic import op


revision: str = "0016_moodle_production_hardening"
down_revision: str | None = "0015_invites_and_admin_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    configured_site_id = os.getenv("MOODLE_INTEGRATION_SITE_ID", "default").strip() or "default"

    if "moodle_submissions" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("moodle_submissions")}
        if "moodle_site_id" not in columns:
            op.add_column(
                "moodle_submissions",
                sa.Column("moodle_site_id", sa.String(length=120), nullable=False, server_default=configured_site_id),
            )
            op.create_index("ix_moodle_submissions_moodle_site_id", "moodle_submissions", ["moodle_site_id"])
        if "reviewer_moodle_user_id" not in columns:
            op.add_column("moodle_submissions", sa.Column("reviewer_moodle_user_id", sa.String(length=255), nullable=True))
        if "reviewer_name" not in columns:
            op.add_column("moodle_submissions", sa.Column("reviewer_name", sa.String(length=255), nullable=True))
        if "reviewed_at" not in columns:
            op.add_column("moodle_submissions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

        constraints = {item["name"] for item in inspector.get_unique_constraints("moodle_submissions")}
        if "uq_moodle_external_submission_id" in constraints:
            op.drop_constraint("uq_moodle_external_submission_id", "moodle_submissions", type_="unique")
        if "uq_moodle_site_external_submission" not in constraints:
            op.create_unique_constraint(
                "uq_moodle_site_external_submission",
                "moodle_submissions",
                ["moodle_site_id", "external_submission_id"],
            )

    if "moodle_user_links" not in inspector.get_table_names():
        op.create_table(
            "moodle_user_links",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("moodle_site_id", sa.String(length=120), nullable=False),
            sa.Column("moodle_user_id", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("moodle_site_id", "moodle_user_id", name="uq_moodle_site_user"),
        )
        op.create_index("ix_moodle_user_links_moodle_site_id", "moodle_user_links", ["moodle_site_id"])
        op.create_index("ix_moodle_user_links_moodle_user_id", "moodle_user_links", ["moodle_user_id"])
        op.create_index("ix_moodle_user_links_user_id", "moodle_user_links", ["user_id"])
        submissions = sa.table(
            "moodle_submissions",
            sa.column("moodle_site_id", sa.String),
            sa.column("moodle_user_id", sa.String),
            sa.column("user_id", sa.String),
        )
        users = sa.table(
            "users",
            sa.column("id", sa.String),
            sa.column("email", sa.String),
            sa.column("full_name", sa.String),
        )
        rows = bind.execute(
            sa.select(
                submissions.c.moodle_site_id,
                submissions.c.moodle_user_id,
                submissions.c.user_id,
                users.c.email,
                users.c.full_name,
            )
            .select_from(submissions.join(users, submissions.c.user_id == users.c.id))
            .distinct()
        ).all()
        now = datetime.now(timezone.utc)
        links: dict[tuple[str, str], dict[str, object]] = {}
        for row in rows:
            key = (row.moodle_site_id, row.moodle_user_id)
            if key in links and links[key]["user_id"] != row.user_id:
                raise RuntimeError(
                    "Cannot backfill Moodle identities: one site/user id is linked to multiple TuneAI users"
                )
            links.setdefault(
                key,
                {
                    "id": str(uuid.uuid4()),
                    "moodle_site_id": row.moodle_site_id,
                    "moodle_user_id": row.moodle_user_id,
                    "user_id": row.user_id,
                    "email": row.email,
                    "full_name": row.full_name,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        if links:
            links_table = sa.table(
                "moodle_user_links",
                sa.column("id", sa.String),
                sa.column("moodle_site_id", sa.String),
                sa.column("moodle_user_id", sa.String),
                sa.column("user_id", sa.String),
                sa.column("email", sa.String),
                sa.column("full_name", sa.String),
                sa.column("created_at", sa.DateTime(timezone=True)),
                sa.column("updated_at", sa.DateTime(timezone=True)),
            )
            op.bulk_insert(links_table, list(links.values()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "moodle_user_links" in inspector.get_table_names():
        op.drop_index("ix_moodle_user_links_user_id", table_name="moodle_user_links")
        op.drop_index("ix_moodle_user_links_moodle_user_id", table_name="moodle_user_links")
        op.drop_index("ix_moodle_user_links_moodle_site_id", table_name="moodle_user_links")
        op.drop_table("moodle_user_links")

    if "moodle_submissions" in inspector.get_table_names():
        constraints = {item["name"] for item in inspector.get_unique_constraints("moodle_submissions")}
        if "uq_moodle_site_external_submission" in constraints:
            op.drop_constraint("uq_moodle_site_external_submission", "moodle_submissions", type_="unique")
        if "uq_moodle_external_submission_id" not in constraints:
            op.create_unique_constraint(
                "uq_moodle_external_submission_id",
                "moodle_submissions",
                ["external_submission_id"],
            )
        columns = {column["name"] for column in inspector.get_columns("moodle_submissions")}
        if "reviewed_at" in columns:
            op.drop_column("moodle_submissions", "reviewed_at")
        if "reviewer_name" in columns:
            op.drop_column("moodle_submissions", "reviewer_name")
        if "reviewer_moodle_user_id" in columns:
            op.drop_column("moodle_submissions", "reviewer_moodle_user_id")
        if "moodle_site_id" in columns:
            op.drop_index("ix_moodle_submissions_moodle_site_id", table_name="moodle_submissions")
            op.drop_column("moodle_submissions", "moodle_site_id")
