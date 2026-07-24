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

