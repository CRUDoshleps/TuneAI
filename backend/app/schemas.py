from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import AnswerStatusEnum, AttemptStatusEnum, RoleEnum, TestStatusEnum, TestTypeEnum


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


class UserRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreateAdmin(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum


class UserRoleUpdate(BaseModel):
    role: RoleEnum
    is_active: bool | None = None


class QuestionCreate(BaseModel):
    text: str = Field(min_length=5)
    expected_answer: str = ""
    order_index: int = 0
    max_score: float = Field(default=10, gt=0)


class QuestionRead(BaseModel):
    id: str
    text: str
    expected_answer: str
    order_index: int
    max_score: float

    model_config = {"from_attributes": True}


class AttemptQuestionRead(BaseModel):
    id: str
    text: str
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
    created_at: datetime
    question_count: int = 0
    questions: list[QuestionRead] = []

    model_config = {"from_attributes": True}


class AssignRequest(BaseModel):
    user_id: str


class AttemptStartRequest(BaseModel):
    test_id: str


class AnswerRead(BaseModel):
    id: str
    question_id: str
    status: AnswerStatusEnum
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
    test_id: str
    question_id: str | None = None
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=20)


class MaterialRead(BaseModel):
    id: str
    test_id: str
    question_id: str | None = None
    title: str
    source_filename: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminDashboard(BaseModel):
    users: int
    tests: int
    attempts: int
    answers_completed: int
    answers_failed: int
    outbox_pending: int


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
