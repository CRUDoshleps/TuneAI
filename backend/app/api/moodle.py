import secrets

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.metrics import ANSWERS_CREATED
from app.models import (
    Answer,
    AnswerStatusEnum,
    AnswerTypeEnum,
    Assignment,
    Attempt,
    MoodleSubmission,
    Question,
    RoleEnum,
    Test,
    TestStatusEnum,
    User,
    new_id,
)
from app.schemas import MoodleManifestQuestion, MoodleManifestRead, MoodleManifestTest, MoodleSubmissionRead, MoodleTextSubmissionRequest
from app.services.outbox import ANSWER_UPLOADED, add_outbox_event
from app.services.storage import StorageService


router = APIRouter(prefix="/integrations/moodle", tags=["moodle"])


def require_moodle_key(x_tuneai_integration_key: str | None = Header(default=None, alias="X-TuneAI-Integration-Key")) -> None:
    settings = get_settings()
    if not settings.moodle_integration_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moodle integration is disabled")
    expected = settings.moodle_integration_token
    if not expected or not x_tuneai_integration_key or not secrets.compare_digest(x_tuneai_integration_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Moodle integration token")


@router.get("/manifest", response_model=MoodleManifestRead)
def get_manifest(
    methodist_email: str | None = Query(default=None, max_length=255),
    test_id: str | None = Query(default=None, max_length=36),
    db: Session = Depends(get_db),
    _: None = Depends(require_moodle_key),
) -> MoodleManifestRead:
    statement = (
        select(Test)
        .where(Test.status == TestStatusEnum.published)
        .options(selectinload(Test.questions), selectinload(Test.owner))
        .order_by(Test.created_at.desc())
    )
    if test_id:
        statement = statement.where(Test.id == test_id)
    if methodist_email:
        statement = statement.join(User, Test.owner_id == User.id).where(User.email == methodist_email.lower())
    tests = db.scalars(statement).all()
    return MoodleManifestRead(
        tests=[
            MoodleManifestTest(
                id=test.id,
                title=test.title,
                description=test.description,
                test_type=test.test_type,
                owner_id=test.owner_id,
                owner_email=test.owner.email,
                owner_name=test.owner.full_name,
                questions=[
                    MoodleManifestQuestion(
                        id=question.id,
                        text=question.text,
                        order_index=question.order_index,
                        max_score=question.max_score,
                        competencies=question.competencies,
                    )
                    for question in sorted(test.questions, key=lambda item: item.order_index)
                ],
            )
            for test in tests
        ]
    )


@router.post("/submissions/text", response_model=MoodleSubmissionRead, status_code=status.HTTP_201_CREATED)
def submit_text(
    payload: MoodleTextSubmissionRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_moodle_key),
) -> MoodleSubmissionRead:
    existing = _load_existing_submission(db, payload.external_submission_id)
    if existing:
        return _serialize_moodle_submission(db, existing)
    test, question = _load_published_test_question(db, payload.test_id, payload.question_id, payload.methodist_email)
    user = _get_or_create_moodle_user(db, payload)
    _ensure_assignment(db, test, user)
    attempt = _get_or_create_attempt(db, test.id, user.id, payload.external_attempt_id)
    answer = _create_answer(
        db,
        attempt=attempt,
        question=question,
        external_submission_id=payload.external_submission_id,
        answer_type=AnswerTypeEnum.text,
        text=payload.text.strip(),
    )
    submission = _create_submission(
        db,
        payload=payload,
        user=user,
        attempt=attempt,
        answer=answer,
    )
    db.commit()
    ANSWERS_CREATED.inc()
    return _serialize_moodle_submission(db, submission)


@router.post("/submissions/audio", response_model=MoodleSubmissionRead, status_code=status.HTTP_201_CREATED)
async def submit_audio(
    external_submission_id: str = Form(...),
    moodle_user_id: str = Form(...),
    user_email: str = Form(...),
    user_full_name: str = Form(...),
    test_id: str = Form(...),
    question_id: str = Form(...),
    external_attempt_id: str | None = Form(default=None),
    moodle_course_id: str | None = Form(default=None),
    moodle_activity_id: str | None = Form(default=None),
    moodle_group_id: str | None = Form(default=None),
    moodle_group_name: str | None = Form(default=None),
    methodist_email: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_moodle_key),
) -> MoodleSubmissionRead:
    existing = _load_existing_submission(db, external_submission_id)
    if existing:
        return _serialize_moodle_submission(db, existing)
    payload = MoodleTextSubmissionRequest(
        external_submission_id=external_submission_id,
        external_attempt_id=external_attempt_id,
        moodle_user_id=moodle_user_id,
        moodle_course_id=moodle_course_id,
        moodle_activity_id=moodle_activity_id,
        moodle_group_id=moodle_group_id,
        moodle_group_name=moodle_group_name,
        methodist_email=methodist_email,
        user_email=user_email,
        user_full_name=user_full_name,
        test_id=test_id,
        question_id=question_id,
        text="audio",
    )
    test, question = _load_published_test_question(db, test_id, question_id, payload.methodist_email)
    user = _get_or_create_moodle_user(db, payload)
    _ensure_assignment(db, test, user)
    attempt = _get_or_create_attempt(db, test.id, user.id, external_attempt_id)
    content = await file.read()
    answer_id = new_id()
    object_key = StorageService().save_audio(answer_id, file, content)
    answer = _create_answer(
        db,
        attempt=attempt,
        question=question,
        external_submission_id=external_submission_id,
        answer_type=AnswerTypeEnum.audio,
        audio_object_key=object_key,
        audio_content_type=file.content_type,
        answer_id=answer_id,
    )
    submission = _create_submission(db, payload=payload, user=user, attempt=attempt, answer=answer)
    db.commit()
    ANSWERS_CREATED.inc()
    return _serialize_moodle_submission(db, submission)


@router.get("/submissions/{external_submission_id}/result", response_model=MoodleSubmissionRead)
def get_submission_result(
    external_submission_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_moodle_key),
) -> MoodleSubmissionRead:
    submission = _load_existing_submission(db, external_submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moodle submission not found")
    return _serialize_moodle_submission(db, submission)


def _load_existing_submission(db: Session, external_submission_id: str) -> MoodleSubmission | None:
    return db.scalar(select(MoodleSubmission).where(MoodleSubmission.external_submission_id == external_submission_id))


def _load_published_test_question(db: Session, test_id: str, question_id: str, methodist_email: str | None = None) -> tuple[Test, Question]:
    test = db.scalar(select(Test).where(Test.id == test_id).options(selectinload(Test.owner)))
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.status != TestStatusEnum.published:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Moodle can submit only published tests")
    if methodist_email and test.owner.email != methodist_email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Test does not belong to the requested methodist")
    question = db.get(Question, question_id)
    if not question or question.test_id != test.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this test")
    return test, question


def _get_or_create_moodle_user(db: Session, payload: MoodleTextSubmissionRequest) -> User:
    email = payload.user_email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(
        email=email,
        full_name=payload.user_full_name,
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        role=RoleEnum.examinee,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_assignment(db: Session, test: Test, user: User) -> None:
    exists = db.scalar(select(Assignment.id).where(Assignment.test_id == test.id, Assignment.user_id == user.id))
    if exists:
        return
    db.add(Assignment(test_id=test.id, user_id=user.id, created_by_id=test.owner_id))
    db.flush()


def _get_or_create_attempt(db: Session, test_id: str, user_id: str, external_attempt_id: str | None) -> Attempt:
    if external_attempt_id:
        existing = db.scalar(
            select(MoodleSubmission)
            .where(
                MoodleSubmission.external_attempt_id == external_attempt_id,
                MoodleSubmission.test_id == test_id,
                MoodleSubmission.user_id == user_id,
            )
            .order_by(MoodleSubmission.created_at.desc())
        )
        if existing:
            attempt = db.get(Attempt, existing.attempt_id)
            if attempt:
                return attempt
    attempt = Attempt(test_id=test_id, user_id=user_id)
    db.add(attempt)
    db.flush()
    return attempt


def _create_answer(
    db: Session,
    *,
    attempt: Attempt,
    question: Question,
    external_submission_id: str,
    answer_type: AnswerTypeEnum,
    text: str | None = None,
    audio_object_key: str | None = None,
    audio_content_type: str | None = None,
    answer_id: str | None = None,
) -> Answer:
    existing_answer = db.scalar(select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id))
    if existing_answer and existing_answer.status != AnswerStatusEnum.failed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already has an answer")
    answer = existing_answer or Answer(id=answer_id or new_id(), attempt_id=attempt.id, question_id=question.id)
    answer.answer_type = answer_type
    answer.idempotency_key = f"moodle:{external_submission_id}"
    answer.text_response = text
    answer.audio_object_key = audio_object_key
    answer.audio_content_type = audio_content_type
    answer.status = AnswerStatusEnum.queued_for_transcription
    answer.error_message = None
    db.add(answer)
    db.flush()
    add_outbox_event(
        db,
        event_type=ANSWER_UPLOADED,
        aggregate_id=answer.id,
        payload={"answer_id": answer.id, "attempt_id": attempt.id, "question_id": question.id},
    )
    return answer


def _create_submission(
    db: Session,
    *,
    payload: MoodleTextSubmissionRequest,
    user: User,
    attempt: Attempt,
    answer: Answer,
) -> MoodleSubmission:
    submission = MoodleSubmission(
        external_submission_id=payload.external_submission_id,
        external_attempt_id=payload.external_attempt_id,
        moodle_user_id=payload.moodle_user_id,
        moodle_course_id=payload.moodle_course_id,
        moodle_activity_id=payload.moodle_activity_id,
        moodle_group_id=payload.moodle_group_id,
        moodle_group_name=payload.moodle_group_name,
        methodist_email=str(payload.methodist_email).lower() if payload.methodist_email else None,
        test_id=payload.test_id,
        question_id=payload.question_id,
        user_id=user.id,
        attempt_id=attempt.id,
        answer_id=answer.id,
    )
    db.add(submission)
    db.flush()
    return submission


def _serialize_moodle_submission(db: Session, submission: MoodleSubmission) -> MoodleSubmissionRead:
    answer = db.get(Answer, submission.answer_id)
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    evaluation = answer.evaluation or {}
    result_ready = answer.status == AnswerStatusEnum.completed
    confidence = evaluation.get("confidence")
    review_required = bool(evaluation.get("review_recommended")) if result_ready else False
    if answer.status == AnswerStatusEnum.failed:
        review_required = True
    teacher_signal = "processing_failed" if answer.status == AnswerStatusEnum.failed else "review_recommended" if review_required else "none"
    question = db.get(Question, submission.question_id)
    max_score = answer.max_score or (question.max_score if question else None)
    score = answer.review_score if answer.review_score is not None else answer.score
    grade = round(score / max_score, 4) if score is not None and max_score else None
    return MoodleSubmissionRead(
        external_submission_id=submission.external_submission_id,
        external_attempt_id=submission.external_attempt_id,
        moodle_course_id=submission.moodle_course_id,
        moodle_activity_id=submission.moodle_activity_id,
        moodle_group_id=submission.moodle_group_id,
        moodle_group_name=submission.moodle_group_name,
        methodist_email=submission.methodist_email,
        test_id=submission.test_id,
        question_id=submission.question_id,
        attempt_id=submission.attempt_id,
        answer_id=submission.answer_id,
        answer_status=answer.status,
        result_ready=result_ready,
        score=score,
        max_score=max_score,
        grade=grade,
        feedback=str(evaluation.get("feedback") or answer.review_feedback or "") or None,
        confidence=float(confidence) if confidence is not None else None,
        review_required=review_required,
        review_reason=_review_reason(answer, evaluation),
        teacher_signal=teacher_signal,
        transcript=answer.transcript,
    )


def _review_reason(answer: Answer, evaluation: dict) -> str | None:
    if answer.status == AnswerStatusEnum.failed:
        return answer.error_message or "Answer processing failed"
    if not evaluation.get("review_recommended"):
        return None
    if evaluation.get("ai_safety", {}).get("detected"):
        return "AI safety policy detected suspicious input"
    if evaluation.get("grounded") is False:
        return "AI answer was not grounded in indexed materials"
    confidence = evaluation.get("confidence")
    if confidence is not None:
        return f"Low AI confidence: {confidence}"
    return "AI recommended teacher review"
