import pytest

from app.models import Material
from app.services.rag import chunk_text, create_material_chunks, retrieve_context


def test_chunk_text_uses_overlap():
    chunks = chunk_text("a" * 2600, chunk_size=1000, overlap=100)
    assert len(chunks) == 3
    assert chunks[0][-100:] == chunks[1][:100]


@pytest.mark.asyncio
async def test_retrieve_context_returns_material_chunks(db_session):
    material = Material(
        test_id="test-id",
        owner_id="owner-id",
        title="Outbox lecture",
        content="Transactional outbox and idempotent message handlers keep distributed processing reliable.",
    )
    db_session.add(material)
    db_session.flush()
    await create_material_chunks(db_session, material)
    db_session.commit()

    context = await retrieve_context(
        db_session,
        test_id="test-id",
        query="Why do we need idempotent handlers and an outbox?",
    )

    assert context
    assert "outbox" in context[0].lower()


@pytest.mark.asyncio
async def test_retrieve_context_uses_test_materials_and_current_question_only(db_session):
    general = Material(
        test_id="test-id",
        owner_id="owner-id",
        title="General",
        content="General context shared by the whole test.",
    )
    first_question = Material(
        test_id="test-id",
        question_id="question-1",
        owner_id="owner-id",
        title="Question 1",
        content="First question private context about retry policies.",
    )
    second_question = Material(
        test_id="test-id",
        question_id="question-2",
        owner_id="owner-id",
        title="Question 2",
        content="Second question private context about forbidden unrelated grading notes.",
    )
    db_session.add_all([general, first_question, second_question])
    db_session.flush()
    await create_material_chunks(db_session, general)
    await create_material_chunks(db_session, first_question)
    await create_material_chunks(db_session, second_question)
    db_session.commit()

    context = await retrieve_context(
        db_session,
        test_id="test-id",
        question_id="question-1",
        query="retry policies",
        limit=10,
    )
    joined = "\n".join(context)

    assert "General context" in joined
    assert "First question private context" in joined
    assert "Second question private context" not in joined
