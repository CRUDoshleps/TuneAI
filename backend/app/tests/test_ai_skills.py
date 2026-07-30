from app.tests.conftest import auth_header, register_and_login


def test_methodist_can_create_upload_update_and_delete_ai_skills(client):
    admin_token = register_and_login(client, "admin@example.com")
    created_methodist = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "methodist@example.com",
            "full_name": "Skill Methodist",
            "password": "password123",
            "role": "methodist",
        },
    )
    assert created_methodist.status_code == 201, created_methodist.text
    methodist_token = register_and_login(client, "methodist@example.com")

    created = client.post(
        "/skills",
        headers=auth_header(methodist_token),
        json={
            "name": "Strict rubric",
            "description": "Penalize vague answers",
            "content": "Lower the score when the learner gives generic statements without concrete course terms.",
        },
    )
    assert created.status_code == 201, created.text
    skill = created.json()
    assert skill["owner_id"] == created_methodist.json()["id"]

    uploaded = client.post(
        "/skills/upload?name=Interview%20signal",
        headers=auth_header(methodist_token),
        files={"file": ("skill.md", b"Ask for clear tradeoffs and reduce score when examples are missing.", "text/markdown")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["source_filename"] == "skill.md"

    listed = client.get("/skills", headers=auth_header(methodist_token))
    assert listed.status_code == 200
    assert {item["name"] for item in listed.json()} == {"Strict rubric", "Interview signal"}

    updated = client.patch(
        f"/skills/{skill['id']}",
        headers=auth_header(methodist_token),
        json={
            "name": "Strict rubric v2",
            "content": "Require exact terminology and lower the score when the answer misses the main definition.",
            "is_active": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/skills/{uploaded.json()['id']}", headers=auth_header(methodist_token))
    assert deleted.status_code == 204


def test_candidate_cannot_manage_ai_skills(client):
    admin_token = register_and_login(client, "admin@example.com")
    created_candidate = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "candidate@example.com",
            "full_name": "Candidate",
            "password": "password123",
            "role": "candidate",
        },
    )
    assert created_candidate.status_code == 201, created_candidate.text
    candidate_token = register_and_login(client, "candidate@example.com")
    response = client.get("/skills", headers=auth_header(candidate_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "Only test creators can manage AI skills"
