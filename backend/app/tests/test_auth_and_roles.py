from app.tests.conftest import auth_header, register_and_login
from app.core.config import get_settings


def test_first_registered_user_is_admin_and_can_create_staff_user(client):
    token = register_and_login(client, "admin@example.com", full_name="Admin User")

    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    created = client.post(
        "/users",
        headers=auth_header(token),
        json={
            "email": "teacher@example.com",
            "full_name": "Teacher User",
            "password": "password123",
            "role": "teacher",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "teacher"


def test_student_can_create_only_self_training_tests(client):
    register_and_login(client, "admin@example.com")
    student_token = register_and_login(client, "student@example.com")

    forbidden = client.post(
        "/tests",
        headers=auth_header(student_token),
        json={
            "title": "Forbidden test",
            "test_type": "exam",
            "questions": [{"text": "Explain safety?", "max_score": 10}],
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Self-training users can create only self-training tests"

    allowed = client.post(
        "/tests",
        headers=auth_header(student_token),
        json={
            "title": "Home training test",
            "test_type": "self_training",
            "questions": [{"text": "Explain retries?", "max_score": 10}],
        },
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["owner_id"]
    assert allowed.json()["questions"][0]["text"] == "Explain retries?"


def test_examinee_cannot_create_tests(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "examinee@example.com",
            "full_name": "Exam Taker",
            "password": "password123",
            "role": "examinee",
        },
    )
    assert created.status_code == 201, created.text
    examinee_token = register_and_login(client, "examinee@example.com")

    response = client.post(
        "/tests",
        headers=auth_header(examinee_token),
        json={
            "title": "Forbidden test",
            "test_type": "self_training",
            "questions": [{"text": "Explain safety?", "max_score": 10}],
        },
    )
    assert response.status_code == 403


def test_first_production_registration_is_student(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    token = register_and_login(client, "production@example.com")
    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "student"
