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
