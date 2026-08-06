from app.tests.conftest import auth_header, register_and_login
from app.core.config import get_settings


def test_admin_uses_separate_registration_and_can_create_staff_user(client):
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


def test_staff_can_bulk_provision_learners_with_generated_password(client):
    admin_token = register_and_login(client, "admin@example.com", full_name="Admin User")
    teacher = client.post(
        "/users",
        headers=auth_header(admin_token),
        json={
            "email": "teacher@example.com",
            "full_name": "Teacher User",
            "password": "password123",
            "role": "teacher",
        },
    )
    assert teacher.status_code == 201, teacher.text
    teacher_token = register_and_login(client, "teacher@example.com", full_name="Teacher User")

    provisioned = client.post(
        "/users/batch",
        headers=auth_header(teacher_token),
        json={
            "users": [
                {"email": "candidate@example.com", "full_name": "Candidate One", "role": "candidate"},
                {"email": "examinee@example.com", "full_name": "Exam Taker", "role": "examinee", "password": "fixedpass123"},
            ]
        },
    )
    assert provisioned.status_code == 201, provisioned.text
    rows = provisioned.json()
    assert [row["user"]["role"] for row in rows] == ["candidate", "examinee"]
    assert rows[0]["password"]
    assert rows[0]["password"] != "fixedpass123"
    assert rows[1]["password"] == "fixedpass123"

    login = client.post("/auth/login", json={"email": "candidate@example.com", "password": rows[0]["password"]})
    assert login.status_code == 200, login.text
    blocked = client.get("/tests", headers=auth_header(login.json()["access_token"]))
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Password change required"
    changed = client.post(
        "/auth/change-password",
        headers=auth_header(login.json()["access_token"]),
        json={"current_password": rows[0]["password"], "new_password": "newpassword123"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    allowed = client.get("/tests", headers=auth_header(login.json()["access_token"]))
    assert allowed.status_code == 200

    forbidden = client.post(
        "/users/batch",
        headers=auth_header(teacher_token),
        json={"users": [{"email": "new-admin@example.com", "full_name": "New Admin", "role": "admin"}]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Batch provisioning is limited to learner accounts"


def test_admin_can_import_users_from_csv(client):
    admin_token = register_and_login(client, "admin@example.com", full_name="Admin User")
    csv_payload = "email,full_name,role,password\ncsv1@example.com,CSV One,examinee,\ncsv2@example.com,CSV Two,candidate,custompass123\n"
    response = client.post(
        "/users/batch/csv",
        headers=auth_header(admin_token),
        files={"file": ("users.csv", csv_payload, "text/csv")},
    )
    assert response.status_code == 201, response.text
    rows = response.json()
    assert [row["user"]["email"] for row in rows] == ["csv1@example.com", "csv2@example.com"]
    assert rows[0]["password"]
    assert rows[1]["password"] == "custompass123"


def test_staff_can_invite_and_reset_password(client):
    admin_token = register_and_login(client, "admin@example.com", full_name="Admin User")
    invite = client.post(
        "/users/invites",
        headers=auth_header(admin_token),
        json={
            "email": "invited@example.com",
            "full_name": "Invited Student",
            "role": "examinee",
            "expires_in_days": 3,
        },
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=", 1)[1]
    accepted = client.post("/auth/invites/accept", json={"token": token, "password": "acceptedpass123"})
    assert accepted.status_code == 200, accepted.text
    login = client.post("/auth/login", json={"email": "invited@example.com", "password": "acceptedpass123"})
    assert login.status_code == 200, login.text

    users = client.get("/users", headers=auth_header(admin_token))
    invited = next(item for item in users.json() if item["email"] == "invited@example.com")
    reset = client.post(f"/users/{invited['id']}/reset-password", headers=auth_header(admin_token))
    assert reset.status_code == 200, reset.text
    assert reset.json()["temporary_password"]
    assert reset.json()["user"]["must_change_password"] is True

    temp_login = client.post("/auth/login", json={"email": "invited@example.com", "password": reset.json()["temporary_password"]})
    assert temp_login.status_code == 200, temp_login.text
    blocked = client.get("/tests", headers=auth_header(temp_login.json()["access_token"]))
    assert blocked.status_code == 403


def test_admin_system_health_reports_operational_checks(client):
    admin_token = register_and_login(client, "admin@example.com", full_name="Admin User")
    response = client.get("/admin/system", headers=auth_header(admin_token))
    assert response.status_code == 200, response.text
    checks = {item["name"]: item for item in response.json()["checks"]}
    assert checks["backend"]["status"] == "ok"
    assert checks["database"]["status"] == "ok"
    assert "ai" in checks
    assert "moodle" in checks


def test_group_assignment_controls_test_visibility_and_attempt_access(client):
    admin_token = register_and_login(client, "admin@example.com", full_name="Admin User")
    provisioned = client.post(
        "/users/batch",
        headers=auth_header(admin_token),
        json={
            "users": [
                {"email": "assigned@example.com", "full_name": "Assigned Student", "role": "examinee", "password": "password123"},
                {"email": "outside@example.com", "full_name": "Outside Student", "role": "examinee", "password": "password123"},
            ]
        },
    )
    assert provisioned.status_code == 201, provisioned.text
    assigned_user = provisioned.json()[0]["user"]

    group = client.post(
        "/groups",
        headers=auth_header(admin_token),
        json={"name": "Oral exam group", "description": "Assigned examinees"},
    )
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]
    member = client.post(
        f"/groups/{group_id}/members",
        headers=auth_header(admin_token),
        json={"user_id": assigned_user["id"]},
    )
    assert member.status_code == 200, member.text
    assert member.json()["members"][0]["email"] == "assigned@example.com"

    test = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Closed oral exam",
            "test_type": "exam",
            "questions": [{"text": "Explain transactional outbox?", "max_score": 10}],
        },
    )
    assert test.status_code == 201, test.text
    test_id = test.json()["id"]
    published = client.patch(f"/tests/{test_id}", headers=auth_header(admin_token), json={"status": "published"})
    assert published.status_code == 200, published.text

    assigned = client.post(f"/tests/{test_id}/assign-group", headers=auth_header(admin_token), json={"group_id": group_id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned_count"] == 1
    assert assigned.json()["skipped_count"] == 0

    assigned_token = register_and_login(client, "assigned@example.com")
    outside_token = register_and_login(client, "outside@example.com")

    assigned_tests = client.get("/tests", headers=auth_header(assigned_token))
    outside_tests = client.get("/tests", headers=auth_header(outside_token))
    assert assigned_tests.status_code == 200
    assert [item["id"] for item in assigned_tests.json()] == [test_id]
    assert assigned_tests.json()[0]["questions"] == []
    assert outside_tests.status_code == 200
    assert outside_tests.json() == []

    outside_attempt = client.post("/attempts", headers=auth_header(outside_token), json={"test_id": test_id})
    assert outside_attempt.status_code == 403
    assert outside_attempt.json()["detail"] == "Test is not assigned to this user"

    assigned_attempt = client.post("/attempts", headers=auth_header(assigned_token), json={"test_id": test_id})
    assert assigned_attempt.status_code == 201, assigned_attempt.text
    assert assigned_attempt.json()["questions"][0]["text"] == "Explain transactional outbox?"


def test_public_registration_never_creates_admin_and_admin_login_is_separate(client):
    public = client.post(
        "/auth/register",
        json={"email": "first@example.com", "password": "password123", "full_name": "First Public"},
    )
    assert public.status_code == 201, public.text
    assert public.json()["role"] == "student"

    admin = client.post(
        "/auth/admin/register",
        json={"email": "admin@example.com", "password": "password123", "full_name": "Admin User"},
    )
    assert admin.status_code == 201, admin.text
    assert admin.json()["role"] == "admin"

    public_admin_login = client.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
    assert public_admin_login.status_code == 403
    assert public_admin_login.json()["detail"] == "Use admin login"

    admin_student_login = client.post("/auth/admin/login", json={"email": "first@example.com", "password": "password123"})
    assert admin_student_login.status_code == 403
    assert admin_student_login.json()["detail"] == "Admin account required"


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
