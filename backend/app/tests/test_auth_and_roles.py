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


def test_self_host_config_can_disable_student_test_creation(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "test_creator_roles", ["teacher", "admin"])
    register_and_login(client, "admin@example.com")
    student_token = register_and_login(client, "student@example.com")

    response = client.post(
        "/tests",
        headers=auth_header(student_token),
        json={
            "title": "No longer allowed",
            "test_type": "self_training",
            "questions": [{"text": "Explain retries?", "max_score": 10}],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only self-training users and staff users can create tests"


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


def test_self_host_config_can_add_student_review_permission(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "answer_reviewer_roles", ["student"])
    register_and_login(client, "admin@example.com")
    student_token = register_and_login(client, "student@example.com")

    response = client.get("/attempts/review-queue", headers=auth_header(student_token))

    assert response.status_code == 200
    assert response.json() == []


def test_admin_can_ban_and_unban_user_but_not_self(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "student@example.com",
            "full_name": "Student User",
            "password": "password123",
            "role": "student",
        },
    )
    assert created.status_code == 201, created.text
    student = created.json()

    banned = client.patch(
        f"/users/{student['id']}",
        headers=auth_header(admin_token),
        json={"role": "student", "is_active": False},
    )
    assert banned.status_code == 200, banned.text
    assert banned.json()["is_active"] is False

    blocked_login = client.post("/auth/login", json={"email": "student@example.com", "password": "password123"})
    assert blocked_login.status_code == 401

    unbanned = client.patch(
        f"/users/{student['id']}",
        headers=auth_header(admin_token),
        json={"role": "student", "is_active": True},
    )
    assert unbanned.status_code == 200, unbanned.text
    assert unbanned.json()["is_active"] is True

    admin = client.get("/auth/me", headers=auth_header(admin_token)).json()
    self_ban = client.patch(
        f"/users/{admin['id']}",
        headers=auth_header(admin_token),
        json={"role": "admin", "is_active": False},
    )
    assert self_ban.status_code == 422
    assert self_ban.json()["detail"] == "Admin cannot deactivate own account"


def test_first_production_registration_is_student(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    token = register_and_login(client, "production@example.com")
    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "student"
