import pytest

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


def test_moodle_owner_allowlist_accepts_csv_values():
    settings = Settings(moodle_integration_owner_emails="one@example.edu,two@example.edu")

    assert settings.moodle_integration_owner_emails == ["one@example.edu", "two@example.edu"]


def test_production_moodle_integration_requires_scoped_credentials():
    settings = Settings(
        app_env="production",
        secret_key="production-secret-key-that-is-not-default",
        yandex_mock=False,
        demo_bootstrap_enabled=False,
        moodle_integration_enabled=True,
        moodle_integration_token="x" * 32,
        moodle_integration_site_id="customer-moodle",
        moodle_integration_owner_emails=["methodist@example.edu"],
    )

    settings.validate_production()

    settings.moodle_integration_owner_emails = []
    with pytest.raises(RuntimeError, match="MOODLE_INTEGRATION_OWNER_EMAILS"):
        settings.validate_production()


def test_production_allows_bounded_public_demo_and_metadata_iam():
    settings = Settings(
        app_env="production",
        secret_key="production-secret-key-that-is-not-default",
        yandex_mock=False,
        yandex_use_metadata_iam=True,
        yandex_folder_id="production-folder",
        demo_bootstrap_enabled=True,
        demo_bootstrap_limit_per_hour=20,
        demo_bootstrap_ttl_hours=6,
    )

    settings.validate_production()


@pytest.mark.parametrize(
    ("limit", "ttl", "message"),
    [
        (0, 6, "DEMO_BOOTSTRAP_LIMIT_PER_HOUR"),
        (61, 6, "DEMO_BOOTSTRAP_LIMIT_PER_HOUR"),
        (20, 0, "DEMO_BOOTSTRAP_TTL_HOURS"),
        (20, 25, "DEMO_BOOTSTRAP_TTL_HOURS"),
    ],
)
def test_production_rejects_unbounded_public_demo(limit, ttl, message):
    settings = Settings(
        app_env="production",
        secret_key="production-secret-key-that-is-not-default",
        yandex_mock=False,
        yandex_use_metadata_iam=True,
        yandex_folder_id="production-folder",
        demo_bootstrap_enabled=True,
        demo_bootstrap_limit_per_hour=limit,
        demo_bootstrap_ttl_hours=ttl,
    )

    with pytest.raises(RuntimeError, match=message):
        settings.validate_production()


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
