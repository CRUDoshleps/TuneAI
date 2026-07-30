from app.core.config import Settings


def test_cors_origins_accept_csv_values():
    settings = Settings(cors_origins="http://localhost:3000, https://exam.example.edu/")

    assert settings.normalized_cors_origins == ["http://localhost:3000", "https://exam.example.edu"]


def test_cors_origins_accept_json_array_values():
    settings = Settings(cors_origins='["http://localhost:3000","https://hr.example.com/"]')

    assert settings.normalized_cors_origins == ["http://localhost:3000", "https://hr.example.com"]


def test_cors_credentials_are_disabled_for_wildcard_origin():
    settings = Settings(cors_origins="*", cors_allow_credentials=True)

    assert settings.normalized_cors_origins == ["*"]
    assert settings.effective_cors_allow_credentials is False


def test_cors_origins_accept_csv_from_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,https://exam.example.edu")

    settings = Settings(_env_file=None)

    assert settings.normalized_cors_origins == ["http://localhost:3000", "https://exam.example.edu"]


def test_permission_roles_accept_csv_and_json_values():
    csv_settings = Settings(test_creator_roles="teacher,admin")
    json_settings = Settings(answer_reviewer_roles='["teacher","interviewer"]')

    assert csv_settings.test_creator_roles == ["teacher", "admin"]
    assert json_settings.answer_reviewer_roles == ["teacher", "interviewer"]


def test_public_tuneai_settings_accept_next_public_aliases(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_PRODUCT_NAME", "Runtime Product")
    monkeypatch.setenv("NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL", "runtime@example.com")

    settings = Settings(_env_file=None)

    assert settings.tuneai_product_name == "Runtime Product"
    assert settings.tuneai_consultation_email == "runtime@example.com"


def test_cors_allows_idempotency_key_header(client):
    response = client.options(
        "/attempts/example/questions/example/text",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )

    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()
