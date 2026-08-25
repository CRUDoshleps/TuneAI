from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0013_assessment_builder_library"
down_revision: str | None = "0012_groups_and_bulk_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        material_scope = sa.Enum("organization", "course", "test", "question", name="materialscopeenum")
        material_scope.create(bind, checkfirst=True)
        for value in ["uploaded", "parsing", "chunking", "embedding"]:
            op.execute(f"ALTER TYPE materialindexstatusenum ADD VALUE IF NOT EXISTS '{value}'")

    material_columns = {column["name"] for column in inspector.get_columns("materials")}
    _add_column_once(material_columns, "materials", sa.Column("organization_id", sa.String(length=120), nullable=True))
    _add_column_once(material_columns, "materials", sa.Column("course_id", sa.String(length=120), nullable=True))
    _add_column_once(material_columns, "materials", sa.Column("content_type", sa.String(length=128), nullable=False, server_default="text/plain"))
    _add_column_once(
        material_columns,
        "materials",
        sa.Column(
            "scope",
            sa.Enum("organization", "course", "test", "question", name="materialscopeenum")
            if bind.dialect.name == "postgresql"
            else sa.String(length=32),
            nullable=False,
            server_default="test",
        ),
    )
    _add_column_once(material_columns, "materials", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    _add_column_once(material_columns, "materials", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("materials") as batch:
        batch.alter_column("test_id", existing_type=sa.String(length=36), nullable=True)
    _create_index_once(inspector, "ix_materials_organization_id", "materials", ["organization_id"])
    _create_index_once(inspector, "ix_materials_course_id", "materials", ["course_id"])

    chunk_columns = {column["name"] for column in inspector.get_columns("material_chunks")}
    _add_column_once(chunk_columns, "material_chunks", sa.Column("organization_id", sa.String(length=120), nullable=True))
    _add_column_once(chunk_columns, "material_chunks", sa.Column("course_id", sa.String(length=120), nullable=True))
    with op.batch_alter_table("material_chunks") as batch:
        batch.alter_column("test_id", existing_type=sa.String(length=36), nullable=True)
    _create_index_once(inspector, "ix_material_chunks_organization_id", "material_chunks", ["organization_id"])
    _create_index_once(inspector, "ix_material_chunks_course_id", "material_chunks", ["course_id"])
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE material_chunks SET organization_id = materials.organization_id, course_id = materials.course_id "
            "FROM materials WHERE material_chunks.material_id = materials.id"
        )
    else:
        op.execute(
            "UPDATE material_chunks SET organization_id = ("
            "SELECT materials.organization_id FROM materials WHERE material_chunks.material_id = materials.id"
            ")"
        )
        op.execute(
            "UPDATE material_chunks SET course_id = ("
            "SELECT materials.course_id FROM materials WHERE material_chunks.material_id = materials.id"
            ")"
        )

    skill_columns = {column["name"] for column in inspector.get_columns("ai_skills")}
    _add_column_once(skill_columns, "ai_skills", sa.Column("scenario", sa.String(length=32), nullable=False, server_default="exam"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("language", sa.String(length=16), nullable=False, server_default="ru"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("strictness", sa.String(length=32), nullable=False, server_default="balanced"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("score_scale", sa.Float(), nullable=False, server_default="10"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.78"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("material_policy", sa.String(length=40), nullable=False, server_default="test_and_question"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("rubric", _json_type(bind), nullable=False, server_default="[]"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("instructions", _json_type(bind), nullable=False, server_default="[]"))
    _add_column_once(skill_columns, "ai_skills", sa.Column("output_config", _json_type(bind), nullable=False, server_default="{}"))

    tables = set(inspector.get_table_names())
    if "generated_question_cache" not in tables:
        op.create_table(
            "generated_question_cache",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("test_id", sa.String(length=36), nullable=False),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("policy", sa.String(length=40), nullable=False),
            sa.Column("requested_count", sa.Integer(), nullable=False),
            sa.Column("source_chunk_ids", _json_type(bind), nullable=False),
            sa.Column("questions", _json_type(bind), nullable=False),
            sa.Column("token_budget_estimate", sa.Integer(), nullable=False),
            sa.Column("reused_count", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("test_id", "fingerprint", name="uq_generated_question_cache_test_fingerprint"),
        )
        op.create_index("ix_generated_question_cache_test_id", "generated_question_cache", ["test_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "generated_question_cache" in tables:
        op.drop_index("ix_generated_question_cache_test_id", table_name="generated_question_cache")
        op.drop_table("generated_question_cache")

    for index_name, table_name in [
        ("ix_material_chunks_course_id", "material_chunks"),
        ("ix_material_chunks_organization_id", "material_chunks"),
        ("ix_materials_course_id", "materials"),
        ("ix_materials_organization_id", "materials"),
    ]:
        _drop_index_once(inspector, index_name, table_name)

    for table_name, column_names in [
        ("material_chunks", ["course_id", "organization_id"]),
        ("materials", ["chunk_count", "version", "scope", "content_type", "course_id", "organization_id"]),
        (
            "ai_skills",
            [
                "output_config",
                "instructions",
                "rubric",
                "material_policy",
                "confidence_threshold",
                "score_scale",
                "strictness",
                "language",
                "scenario",
            ],
        ),
    ]:
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in column_names:
            if column_name in existing:
                op.drop_column(table_name, column_name)

    if bind.dialect.name == "postgresql":
        sa.Enum("organization", "course", "test", "question", name="materialscopeenum").drop(bind, checkfirst=True)


def _json_type(bind):
    return postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()


def _add_column_once(existing_columns: set[str], table_name: str, column: sa.Column) -> None:
    if column.name not in existing_columns:
        op.add_column(table_name, column)
        existing_columns.add(column.name)


def _create_index_once(inspector, index_name: str, table_name: str, columns: list[str]) -> None:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_once(inspector, index_name: str, table_name: str) -> None:
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table_name)
