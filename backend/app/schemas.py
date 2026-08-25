from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import AIProviderEnum, AnswerStatusEnum, AnswerTypeEnum, AttemptStatusEnum, MaterialIndexStatusEnum, MaterialScopeEnum, QuestionAnswerModeEnum, QuestionTypeEnum, RoleEnum, SourceImportStatusEnum, TestStatusEnum, TestTypeEnum


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=24, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool
    must_change_password: bool = False
    is_demo: bool = False
    expires_at: datetime | None = None
    created_by_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreateAdmin(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum


class UserCreateStaff(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum = RoleEnum.student


class UserProvisionCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: RoleEnum = RoleEnum.examinee


class UserBatchCreate(BaseModel):
    users: list[UserProvisionCreate] = Field(min_length=1, max_length=200)


class UserProvisionRead(BaseModel):
    user: UserRead
    password: str


class UserInviteCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    role: RoleEnum = RoleEnum.examinee
    expires_in_days: int = Field(default=7, ge=1, le=90)


class UserInviteRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: RoleEnum
    invite_url: str
    expires_at: datetime
    accepted_at: datetime | None = None


class PasswordResetRead(BaseModel):
    user: UserRead
    temporary_password: str


class UserRoleUpdate(BaseModel):
    role: RoleEnum
    is_active: bool | None = None


class QuestionCompetency(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1, gt=0)


class RubricCriterion(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1, gt=0)


class SkillOutputConfig(BaseModel):
    require_sources: bool = True
    require_recommendations: bool = True
    require_manual_review_reason: bool = True


class QuestionOption(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)


class SourceReference(BaseModel):
    source_import_id: str | None = None
    segment_id: str
    label: str = ""


class QuestionCreate(BaseModel):
    text: str = Field(min_length=5)
    expected_answer: str = ""
    question_type: QuestionTypeEnum = QuestionTypeEnum.open_response
    options: list[QuestionOption] = Field(default_factory=list)
    correct_option_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    source_refs: list[SourceReference] = Field(default_factory=list)
    competencies: list[QuestionCompetency] = []
    answer_mode: QuestionAnswerModeEnum = QuestionAnswerModeEnum.both
    order_index: int = 0
    max_score: float = Field(default=10, gt=0)

    @model_validator(mode="after")
    def validate_options(self):
        _validate_question_options(self.question_type, self.options, self.correct_option_ids)
        return self


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=5)
    expected_answer: str | None = None
    question_type: QuestionTypeEnum | None = None
    options: list[QuestionOption] | None = None
    correct_option_ids: list[str] | None = None
    explanation: str | None = None
    source_refs: list[SourceReference] | None = None
    competencies: list[QuestionCompetency] | None = None
    answer_mode: QuestionAnswerModeEnum | None = None
    order_index: int | None = None
    max_score: float | None = Field(default=None, gt=0)


class QuestionReorderRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1)


class QuestionRead(BaseModel):
    id: str
    text: str
    expected_answer: str
    question_type: QuestionTypeEnum = QuestionTypeEnum.open_response
    options: list[QuestionOption] = Field(default_factory=list)
    correct_option_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    source_refs: list[SourceReference] = Field(default_factory=list)
    competencies: list[QuestionCompetency] = []
    answer_mode: QuestionAnswerModeEnum = QuestionAnswerModeEnum.both
    order_index: int
    max_score: float

    model_config = {"from_attributes": True}


class AttemptQuestionRead(BaseModel):
    id: str
    text: str
    question_type: QuestionTypeEnum = QuestionTypeEnum.open_response
    options: list[QuestionOption] = Field(default_factory=list)
    competencies: list[QuestionCompetency] = []
    answer_mode: QuestionAnswerModeEnum = QuestionAnswerModeEnum.both
    order_index: int
    max_score: float

    model_config = {"from_attributes": True}


class TestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    test_type: TestTypeEnum
    criteria: dict[str, Any] = Field(default_factory=dict)
    time_limit_seconds: int | None = Field(default=None, gt=0)
    questions: list[QuestionCreate] = Field(default_factory=list)


class TestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    status: TestStatusEnum | None = None
    criteria: dict[str, Any] | None = None
    time_limit_seconds: int | None = Field(default=None, gt=0)


class TestRead(BaseModel):
    id: str
    title: str
    description: str
    test_type: TestTypeEnum
    status: TestStatusEnum
    criteria: dict[str, Any]
    time_limit_seconds: int | None
    owner_id: str
    is_demo: bool = False
    expires_at: datetime | None = None
    created_at: datetime
    question_count: int = 0
    questions: list[QuestionRead] = []

    model_config = {"from_attributes": True}


class AISkillCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    content: str = Field(min_length=20, max_length=50000)
    scenario: Literal["exam", "self_training", "interview"] = "exam"
    language: str = Field(default="ru", min_length=2, max_length=16)
    strictness: Literal["soft", "balanced", "strict"] = "balanced"
    score_scale: float = Field(default=10, gt=0, le=100)
    confidence_threshold: float = Field(default=0.78, ge=0, le=1)
    material_policy: Literal["test_and_question", "question_only", "course_library", "organization_library", "none"] = "test_and_question"
    rubric: list[RubricCriterion] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list, max_length=20)
    output: SkillOutputConfig = Field(default_factory=SkillOutputConfig)
    is_active: bool = True


class AISkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, min_length=20, max_length=50000)
    scenario: Literal["exam", "self_training", "interview"] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=16)
    strictness: Literal["soft", "balanced", "strict"] | None = None
    score_scale: float | None = Field(default=None, gt=0, le=100)
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    material_policy: Literal["test_and_question", "question_only", "course_library", "organization_library", "none"] | None = None
    rubric: list[RubricCriterion] | None = None
    instructions: list[str] | None = Field(default=None, max_length=20)
    output: SkillOutputConfig | None = None
    is_active: bool | None = None


class AISkillRead(BaseModel):
    id: str
    name: str
    description: str
    content: str
    scenario: str = "exam"
    language: str = "ru"
    strictness: str = "balanced"
    score_scale: float = 10
    confidence_threshold: float = 0.78
    material_policy: str = "test_and_question"
    rubric: list[RubricCriterion] = []
    instructions: list[str] = []
    output_config: dict[str, Any] = {}
    source_filename: str | None = None
    owner_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignRequest(BaseModel):
    user_id: str


class GroupAssignRequest(BaseModel):
    group_id: str


class GroupAssignRead(BaseModel):
    group_id: str
    test_id: str
    assigned_count: int
    skipped_count: int


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)


class GroupMemberAdd(BaseModel):
    user_id: str


class GroupMemberRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool


class GroupRead(BaseModel):
    id: str
    name: str
    description: str
    created_by_id: str
    created_at: datetime
    members: list[GroupMemberRead] = []


class AttemptStartRequest(BaseModel):
    test_id: str


class AnswerRead(BaseModel):
    id: str
    question_id: str
    answer_type: AnswerTypeEnum = AnswerTypeEnum.audio
    status: AnswerStatusEnum
    text_response: str | None = None
    selected_option_ids: list[str] = Field(default_factory=list)
    transcript: str | None = None
    evaluation: dict[str, Any] | None = None
    score: float | None = None
    max_score: float | None = None
    review_score: float | None = None
    review_feedback: str | None = None
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class AttemptRead(BaseModel):
    id: str
    test_id: str
    user_id: str
    status: AttemptStatusEnum
    total_score: float | None = None
    max_score: float | None = None
    started_at: datetime
    completed_at: datetime | None = None
    answers: list[AnswerRead] = []
    questions: list[AttemptQuestionRead] = []

    model_config = {"from_attributes": True}


class TextAnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class ChoiceAnswerRequest(BaseModel):
    selected_option_ids: list[str] = Field(min_length=1, max_length=50)


class AnswerResultRead(BaseModel):
    answer_id: str
    question_id: str
    status: AnswerStatusEnum
    answer_type: AnswerTypeEnum
    transcript: str | None = None
    score: float | None = None
    max_score: float | None = None
    feedback: str | None = None
    mistakes: list[str] = []
    missing_points: list[str] = []
    recommendations: str | None = None
    source_excerpts: list[str] = []
    confidence: float | None = None
    review_status: Literal["not_ready", "ai_final", "review_recommended", "reviewed"] = "not_ready"


class AttemptResultRead(BaseModel):
    id: str
    attempt_id: str
    test_id: str
    user_id: str
    status: AttemptStatusEnum
    total_score: float | None = None
    max_score: float | None = None
    questions: list[AttemptQuestionRead] = []
    answers: list[AnswerResultRead]


class EvaluationResult(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    correct_points: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    feedback: str
    recommendations: str
    confidence: float = Field(ge=0, le=1)
    source_excerpts: list[str] = Field(default_factory=list)
    competency_scores: dict[str, float] = Field(default_factory=dict)
    grounded: bool = False
    review_recommended: bool = False
    evaluation_version: str = "tuneai-rubric-v1"

    @model_validator(mode="after")
    def keep_score_within_rubric(self) -> "EvaluationResult":
        self.score = min(self.score, self.max_score)
        self.source_excerpts = [excerpt.strip()[:600] for excerpt in self.source_excerpts if excerpt.strip()][:3]
        return self


class AIReadiness(BaseModel):
    status: Literal["ready", "configuration_required"]
    mode: Literal["mock", "real"]
    configured: bool
    provider: str = "Yandex AI Studio"
    capabilities: list[str]
    review_confidence_threshold: float
    disclosure: str


class AIProviderConfigCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider: AIProviderEnum
    is_enabled: bool = True
    is_active: bool = False
    credentials: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class AIProviderConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    is_enabled: bool | None = None
    is_active: bool | None = None
    credentials: dict[str, str | None] | None = None
    config: dict[str, Any] | None = None


class AIProviderConfigRead(BaseModel):
    id: str
    name: str
    provider: AIProviderEnum
    is_enabled: bool
    is_active: bool
    credentials_masked: dict[str, str]
    config: dict[str, Any]
    created_by_id: str
    created_at: datetime
    updated_at: datetime


class SuspiciousAIInputRead(BaseModel):
    detected: bool
    patterns: list[str] = []


class CompetencyMetricRead(BaseModel):
    name: str
    score: float
    max_score: float
    completed_answers: int
    recommendations: list[str] = []


class PublicConfigRead(BaseModel):
    config: dict[str, Any]


class DemoBootstrapRequest(BaseModel):
    scenario_id: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=120)
    test_type: TestTypeEnum
    role_label: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    question: str = Field(min_length=5)
    expected_answer: str = ""
    agent_profile: str = "rubric-rag-reviewer"
    competencies: list[str] = []


class DemoBootstrapRead(BaseModel):
    tokens: TokenPair
    user: UserRead
    test: TestRead
    attempt: AttemptRead | None = None


class AnswerReviewRequest(BaseModel):
    score: float = Field(ge=0)
    feedback: str = Field(min_length=3, max_length=4000)


class ReviewQueueItem(BaseModel):
    answer_id: str
    attempt_id: str
    test_title: str
    question_text: str
    student_email: str
    transcript: str
    ai_score: float
    max_score: float
    confidence: float
    ai_feedback: str
    source_excerpts: list[str]
    created_at: datetime


class MaterialCreate(BaseModel):
    test_id: str | None = None
    question_id: str | None = None
    organization_id: str | None = Field(default=None, max_length=120)
    course_id: str | None = Field(default=None, max_length=120)
    scope: MaterialScopeEnum = MaterialScopeEnum.test
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=20, max_length=5 * 1024 * 1024)
    content_type: str = Field(default="text/plain", max_length=128)
    version: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_scope_links(self) -> "MaterialCreate":
        if self.scope in {MaterialScopeEnum.test, MaterialScopeEnum.question} and not self.test_id:
            raise ValueError("test_id is required for test and question materials")
        if self.scope == MaterialScopeEnum.question and not self.question_id:
            raise ValueError("question_id is required for question materials")
        if self.scope == MaterialScopeEnum.course and not self.course_id:
            raise ValueError("course_id is required for course library materials")
        if self.scope == MaterialScopeEnum.organization and not self.organization_id:
            raise ValueError("organization_id is required for organization library materials")
        return self


class MaterialRead(BaseModel):
    id: str
    organization_id: str | None = None
    course_id: str | None = None
    test_id: str | None = None
    question_id: str | None = None
    title: str
    source_filename: str | None = None
    content_type: str = "text/plain"
    scope: MaterialScopeEnum = MaterialScopeEnum.test
    version: int = 1
    index_status: MaterialIndexStatusEnum = MaterialIndexStatusEnum.uploaded
    index_error: str | None = None
    chunk_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedQuestionCandidate(BaseModel):
    text: str
    expected_answer: str = ""
    question_type: QuestionTypeEnum = QuestionTypeEnum.open_response
    options: list[QuestionOption] = Field(default_factory=list)
    correct_option_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    source_refs: list[SourceReference] = Field(default_factory=list)
    competencies: list[QuestionCompetency] = []
    answer_mode: QuestionAnswerModeEnum = QuestionAnswerModeEnum.both
    max_score: float = 10
    source_excerpt: str = ""
    novelty_score: float = 0
    reused: bool = False


class QuestionGenerationRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    material_policy: Literal["test_and_question", "question_only", "course_library", "organization_library"] = "test_and_question"
    question_id: str | None = None
    reuse_existing: bool = True
    max_context_chunks: int = Field(default=10, ge=1, le=40)
    max_tokens_budget: int = Field(default=1400, ge=300, le=8000)


class QuestionGenerationRead(BaseModel):
    questions: list[GeneratedQuestionCandidate]
    reused_count: int
    source_chunk_count: int
    token_budget_estimate: int
    fingerprint: str


class CalibrationExample(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    answer: str = Field(min_length=1, max_length=20000)


class CalibrationPreviewRequest(BaseModel):
    skill_id: str | None = None
    question_id: str | None = None
    examples: list[CalibrationExample] = Field(min_length=1, max_length=5)


class CalibrationPreviewItem(BaseModel):
    label: str
    score: float
    max_score: float
    confidence: float
    feedback: str
    source_excerpts: list[str] = []
    manual_review_reason: str | None = None


class CalibrationPreviewRead(BaseModel):
    skill_id: str | None = None
    material_policy: str
    items: list[CalibrationPreviewItem]
    token_budget_estimate: int
    reused_rag_context: bool


class MoodleTextSubmissionRequest(BaseModel):
    external_submission_id: str = Field(min_length=2, max_length=255)
    external_attempt_id: str | None = Field(default=None, max_length=255)
    moodle_user_id: str = Field(min_length=1, max_length=255)
    moodle_course_id: str | None = Field(default=None, max_length=255)
    moodle_activity_id: str | None = Field(default=None, max_length=255)
    moodle_group_id: str | None = Field(default=None, max_length=255)
    moodle_group_name: str | None = Field(default=None, max_length=255)
    methodist_email: EmailStr | None = None
    user_email: EmailStr
    user_full_name: str = Field(min_length=2, max_length=255)
    test_id: str
    question_id: str
    text: str = Field(min_length=1, max_length=20000)


class MoodleSubmissionRead(BaseModel):
    moodle_site_id: str
    external_submission_id: str
    external_attempt_id: str | None = None
    moodle_course_id: str | None = None
    moodle_activity_id: str | None = None
    moodle_group_id: str | None = None
    moodle_group_name: str | None = None
    methodist_email: EmailStr | None = None
    test_id: str
    question_id: str
    attempt_id: str
    answer_id: str
    answer_status: AnswerStatusEnum
    result_ready: bool
    score: float | None = None
    max_score: float | None = None
    grade: float | None = None
    feedback: str | None = None
    confidence: float | None = None
    review_required: bool = False
    review_reason: str | None = None
    teacher_signal: Literal["none", "review_recommended", "processing_failed"] = "none"
    transcript: str | None = None


class MoodleSubmissionReviewRequest(BaseModel):
    score: float = Field(ge=0)
    feedback: str = Field(min_length=1, max_length=10000)
    reviewer_moodle_user_id: str = Field(min_length=1, max_length=255)
    reviewer_name: str = Field(min_length=2, max_length=255)


class MoodleManifestQuestion(BaseModel):
    id: str
    text: str
    order_index: int
    max_score: float
    answer_mode: QuestionAnswerModeEnum = QuestionAnswerModeEnum.both
    competencies: list[QuestionCompetency] = []


class MoodleManifestTest(BaseModel):
    id: str
    title: str
    description: str
    test_type: TestTypeEnum
    owner_id: str
    owner_email: EmailStr
    owner_name: str
    questions: list[MoodleManifestQuestion]


class MoodleManifestRead(BaseModel):
    tests: list[MoodleManifestTest]


class AdminDashboard(BaseModel):
    users: int
    tests: int
    attempts: int
    answers_completed: int
    answers_failed: int
    outbox_pending: int
    attempts_completed: int = 0
    average_score_percent: float = 0
    review_pending: int = 0


class AdminAttemptRead(BaseModel):
    id: str
    test_id: str
    test_title: str
    user_id: str
    user_email: str
    status: AttemptStatusEnum
    total_score: float | None = None
    max_score: float | None = None
    answers_total: int
    answers_completed: int
    answers_failed: int
    started_at: datetime
    completed_at: datetime | None = None


class AdminFailedJobRead(BaseModel):
    id: str
    kind: str
    status: str
    aggregate_id: str | None = None
    user_email: str | None = None
    test_title: str | None = None
    error_message: str
    created_at: datetime | None = None


class SystemHealthCheck(BaseModel):
    name: str
    status: Literal["ok", "warning", "error"]
    detail: str


class SystemHealthRead(BaseModel):
    checks: list[SystemHealthCheck]
    generated_at: datetime


class SourceSegmentRead(BaseModel):
    id: str
    index: int
    title: str = ""
    text: str = ""
    notes: str = ""


class SourceImportGenerateRequest(BaseModel):
    count: int = Field(default=8, ge=1, le=30)
    difficulty: Literal["easy", "balanced", "hard"] = "balanced"
    language: str = Field(default="ru", min_length=2, max_length=12)
    question_types: list[QuestionTypeEnum] = Field(default_factory=lambda: [QuestionTypeEnum.open_response, QuestionTypeEnum.single_choice])
    excluded_segment_ids: list[str] = Field(default_factory=list)


class SourceImportRead(BaseModel):
    id: str
    test_id: str
    owner_id: str
    source_filename: str
    content_type: str
    status: SourceImportStatusEnum
    segments: list[SourceSegmentRead] = Field(default_factory=list)
    excluded_segment_ids: list[str] = Field(default_factory=list)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditLogRead(BaseModel):
    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


def _validate_question_options(question_type: QuestionTypeEnum, options: list[QuestionOption], correct_ids: list[str]) -> None:
    if question_type == QuestionTypeEnum.open_response:
        return
    if len(options) < 2:
        raise ValueError("Choice questions require at least two options")
    option_ids = [item.id for item in options]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError("Option ids must be unique")
    if not correct_ids or not set(correct_ids).issubset(option_ids):
        raise ValueError("Correct option ids must reference available options")
    if question_type == QuestionTypeEnum.single_choice and len(correct_ids) != 1:
        raise ValueError("Single choice question requires exactly one correct option")
