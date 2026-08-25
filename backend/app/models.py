import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_type() -> Any:
    return JSON().with_variant(JSONB, "postgresql")


class RoleEnum(str, enum.Enum):
    student = "student"
    examinee = "examinee"
    candidate = "candidate"
    methodist = "methodist"
    teacher = "teacher"
    interviewer = "interviewer"
    admin = "admin"


class TestTypeEnum(str, enum.Enum):
    exam = "exam"
    self_training = "self_training"
    interview = "interview"


class TestStatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class AttemptStatusEnum(str, enum.Enum):
    started = "started"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnswerStatusEnum(str, enum.Enum):
    uploaded = "uploaded"
    queued_for_transcription = "queued_for_transcription"
    transcribing = "transcribing"
    transcribed = "transcribed"
    rag_processing = "rag_processing"
    evaluating = "evaluating"
    completed = "completed"
    failed = "failed"


class AnswerTypeEnum(str, enum.Enum):
    audio = "audio"
    text = "text"
    choice = "choice"


class QuestionAnswerModeEnum(str, enum.Enum):
    audio = "audio"
    text = "text"
    both = "both"


class QuestionTypeEnum(str, enum.Enum):
    open_response = "open_response"
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"


class SourceImportStatusEnum(str, enum.Enum):
    uploaded = "uploaded"
    ready = "ready"
    queued = "queued"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class MaterialIndexStatusEnum(str, enum.Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    pending = "pending"
    indexed = "indexed"
    failed = "failed"


class MaterialScopeEnum(str, enum.Enum):
    organization = "organization"
    course = "course"
    test = "test"
    question = "question"


class AIProviderEnum(str, enum.Enum):
    mock = "mock"
    yandex = "yandex"
    openai_compatible = "openai_compatible"
    local = "local"


class OutboxStatusEnum(str, enum.Enum):
    pending = "pending"
    published = "published"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.student, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owned_tests: Mapped[list["Test"]] = relationship(back_populates="owner", foreign_keys="Test.owner_id")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="user")
    created_groups: Mapped[list["Group"]] = relationship(back_populates="created_by", foreign_keys="Group.created_by_id")


class UserInvite(Base):
    __tablename__ = "user_invites"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_invite_token_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.examinee, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_type: Mapped[TestTypeEnum] = mapped_column(Enum(TestTypeEnum), nullable=False)
    status: Mapped[TestStatusEnum] = mapped_column(Enum(TestStatusEnum), default=TestStatusEnum.draft, nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    owner: Mapped[User] = relationship(back_populates="owned_tests", foreign_keys=[owner_id])
    questions: Mapped[list["Question"]] = relationship(back_populates="test", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="test", cascade="all, delete-orphan")
    materials: Mapped[list["Material"]] = relationship(back_populates="test", cascade="all, delete-orphan")


class AISkill(Base):
    __tablename__ = "ai_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str] = mapped_column(String(32), default="exam", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ru", nullable=False)
    strictness: Mapped[str] = mapped_column(String(32), default="balanced", nullable=False)
    score_scale: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.78, nullable=False)
    material_policy: Mapped[str] = mapped_column(String(40), default="test_and_question", nullable=False)
    rubric: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    instructions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    output_config: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("test_id", "order_index", name="uq_question_order_per_test"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    question_type: Mapped[QuestionTypeEnum] = mapped_column(
        Enum(QuestionTypeEnum), default=QuestionTypeEnum.open_response, nullable=False
    )
    options: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    correct_option_ids: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    competencies: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    answer_mode: Mapped[QuestionAnswerModeEnum] = mapped_column(
        Enum(QuestionAnswerModeEnum),
        default=QuestionAnswerModeEnum.both,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    test: Mapped[Test] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(back_populates="question")
    materials: Mapped[list["Material"]] = relationship(back_populates="question")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("test_id", "user_id", name="uq_assignment_test_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    test: Mapped[Test] = relationship(back_populates="assignments", foreign_keys=[test_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    created_by: Mapped[User] = relationship(back_populates="created_groups", foreign_keys=[created_by_id])
    memberships: Mapped[list["GroupMembership"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    added_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    group: Mapped[Group] = relationship(back_populates="memberships", foreign_keys=[group_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    added_by: Mapped[User] = relationship(foreign_keys=[added_by_id])


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[AttemptStatusEnum] = mapped_column(Enum(AttemptStatusEnum), default=AttemptStatusEnum.started, nullable=False)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    test: Mapped[Test] = relationship()
    user: Mapped[User] = relationship(back_populates="attempts")
    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class MoodleSubmission(Base):
    __tablename__ = "moodle_submissions"
    __table_args__ = (
        UniqueConstraint("moodle_site_id", "external_submission_id", name="uq_moodle_site_external_submission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    moodle_site_id: Mapped[str] = mapped_column(String(120), nullable=False, default="default", index=True)
    external_submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_attempt_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    moodle_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    moodle_course_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    moodle_activity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    moodle_group_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    moodle_group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    methodist_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), nullable=False)
    reviewer_moodle_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MoodleUserLink(Base):
    __tablename__ = "moodle_user_links"
    __table_args__ = (
        UniqueConstraint("moodle_site_id", "moodle_user_id", name="uq_moodle_site_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    moodle_site_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    moodle_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    answer_type: Mapped[AnswerTypeEnum] = mapped_column(Enum(AnswerTypeEnum), default=AnswerTypeEnum.audio, nullable=False)
    status: Mapped[AnswerStatusEnum] = mapped_column(
        Enum(AnswerStatusEnum), default=AnswerStatusEnum.uploaded, nullable=False
    )
    audio_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_option_ids: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(json_type()), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship(back_populates="answers")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    course_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    test_id: Mapped[str | None] = mapped_column(ForeignKey("tests.id"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(128), default="text/plain", nullable=False)
    scope: Mapped[MaterialScopeEnum] = mapped_column(Enum(MaterialScopeEnum), default=MaterialScopeEnum.test, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[MaterialIndexStatusEnum] = mapped_column(
        Enum(MaterialIndexStatusEnum), default=MaterialIndexStatusEnum.uploaded, nullable=False
    )
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    test: Mapped[Test | None] = relationship(back_populates="materials")
    question: Mapped[Question | None] = relationship(back_populates="materials")
    chunks: Mapped[list["MaterialChunk"]] = relationship(back_populates="material", cascade="all, delete-orphan")


class MaterialChunk(Base):
    __tablename__ = "material_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    course_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    test_id: Mapped[str | None] = mapped_column(ForeignKey("tests.id"), nullable=True, index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)

    material: Mapped[Material] = relationship(back_populates="chunks")


class SourceImport(Base):
    __tablename__ = "source_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[SourceImportStatusEnum] = mapped_column(
        Enum(SourceImportStatusEnum), default=SourceImportStatusEnum.uploaded, nullable=False, index=True
    )
    segments: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    excluded_segment_ids: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    generation_config: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    test: Mapped[Test] = relationship()
    owner: Mapped[User] = relationship()


class GeneratedQuestionCache(Base):
    __tablename__ = "generated_question_cache"
    __table_args__ = (UniqueConstraint("test_id", "fingerprint", name="uq_generated_question_cache_test_fingerprint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id"), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_chunk_ids: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    token_budget_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reused_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[AIProviderEnum] = mapped_column(Enum(AIProviderEnum), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    credentials: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    status: Mapped[OutboxStatusEnum] = mapped_column(Enum(OutboxStatusEnum), default=OutboxStatusEnum.pending, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    actor: Mapped[User | None] = relationship()
