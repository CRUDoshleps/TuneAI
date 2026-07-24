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
