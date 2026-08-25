import asyncio

from app.db.session import SessionLocal
from app.models import Material
from app.services.ai_skills import render_skill_instructions
from app.services.rag import index_material
from app.tests.conftest import auth_header, register_and_login


def test_assessment_builder_generates_questions_with_rag_cache_and_calibrates(client):
    admin_token = register_and_login(client, "admin@example.com")
    skill = client.post(
        "/skills",
        headers=auth_header(admin_token),
        json={
            "name": "Strict Oral Exam Reviewer",
            "description": "Fact-focused oral exam evaluator",
            "content": "Use the rubric and course materials. Lower score when the answer has vague claims without source support.",
            "scenario": "exam",
            "language": "ru",
            "strictness": "strict",
            "score_scale": 10,
            "confidence_threshold": 0.82,
            "material_policy": "course_library",
            "rubric": [
                {"name": "factual_accuracy", "weight": 0.45},
                {"name": "completeness", "weight": 0.25},
            ],
            "instructions": [
                "Оценивай только по материалам курса.",
                "Не засчитывай общие рассуждения без фактов.",
            ],
            "output": {
                "require_sources": True,
                "require_recommendations": True,
                "require_manual_review_reason": True,
            },
        },
    )
    assert skill.status_code == 201, skill.text
    assert skill.json()["strictness"] == "strict"
    assert skill.json()["material_policy"] == "course_library"

    test = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Distributed systems oral exam",
            "test_type": "exam",
            "criteria": {
                "course_id": "distributed-systems",
                "organization_id": "faculty",
                "material_policy": "course_library",
                "skill_ids": [skill.json()["id"]],
            },
            "questions": [
                {
                    "text": "Explain transactional outbox.",
                    "expected_answer": "Atomic write and later event publishing.",
                    "max_score": 10,
                }
            ],
        },
    )
    assert test.status_code == 201, test.text
    test_id = test.json()["id"]

    material = client.post(
        "/materials",
        headers=auth_header(admin_token),
        json={
            "test_id": test_id,
            "scope": "course",
            "course_id": "distributed-systems",
            "title": "Course reliability notes",
            "content": (
                "Transactional outbox persists the domain change and outgoing event in the same database transaction. "
                "Idempotent consumers deduplicate repeated messages and make retry processing safe. "
                "A relay publishes pending outbox rows asynchronously and marks them delivered after broker acknowledgement."
            ),
        },
    )
    assert material.status_code == 201, material.text
    assert material.json()["scope"] == "course"
    assert material.json()["index_status"] == "uploaded"

    with SessionLocal() as db:
        indexed = asyncio.run(index_material(db, material.json()["id"]))
        assert indexed.chunk_count > 0

    generated = client.post(
        f"/tests/{test_id}/generate-questions",
        headers=auth_header(admin_token),
        json={
            "count": 3,
            "material_policy": "course_library",
            "reuse_existing": True,
            "max_context_chunks": 4,
            "max_tokens_budget": 600,
        },
    )
    assert generated.status_code == 200, generated.text
    first_generation = generated.json()
    assert first_generation["questions"]
    assert first_generation["source_chunk_count"] > 0
    assert first_generation["token_budget_estimate"] <= 600
    assert "Объясните своими словами" in first_generation["questions"][0]["text"]
    assert first_generation["questions"][0]["answer_mode"] == "both"

    cached = client.post(
        f"/tests/{test_id}/generate-questions",
        headers=auth_header(admin_token),
        json={
            "count": 3,
            "material_policy": "course_library",
            "reuse_existing": True,
            "max_context_chunks": 4,
            "max_tokens_budget": 600,
        },
    )
    assert cached.status_code == 200, cached.text
    assert cached.json()["fingerprint"] == first_generation["fingerprint"]
    assert cached.json()["reused_count"] == len(first_generation["questions"])

    preview = client.post(
        f"/tests/{test_id}/calibration-preview",
        headers=auth_header(admin_token),
        json={
            "skill_id": skill.json()["id"],
            "examples": [
                {"label": "good", "answer": "Outbox stores the event with the aggregate update and a relay publishes it later."},
                {"label": "weak", "answer": "It is just a queue."},
            ],
        },
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["material_policy"] == "course_library"
    assert payload["reused_rag_context"] is True
    assert len(payload["items"]) == 2
    assert payload["items"][0]["source_excerpts"]

    with SessionLocal() as db:
        row = db.get(Material, material.json()["id"])
        assert row is not None


def test_structured_skill_render_is_compact(client):
    admin_token = register_and_login(client, "admin@example.com")
    response = client.post(
        "/skills",
        headers=auth_header(admin_token),
        json={
            "name": "Fact checker",
            "description": "Requires source-backed facts",
            "content": "Check facts against RAG context and ask for manual review when evidence is weak.",
            "material_policy": "test_and_question",
            "rubric": [{"name": "facts", "weight": 0.7}],
            "instructions": ["Use source excerpts.", "Do not reward unsupported guesses."],
            "output": {
                "require_sources": True,
                "require_recommendations": False,
                "require_manual_review_reason": True,
            },
        },
    )
    assert response.status_code == 201, response.text

    with SessionLocal() as db:
        from app.models import AISkill

        skill = db.get(AISkill, response.json()["id"])
        rendered = render_skill_instructions(skill)

    assert "material_policy=test_and_question" in rendered
    assert "facts:0.7" in rendered
    assert "require_sources" in rendered
    assert "require_recommendations" not in rendered
