from app.tests.conftest import auth_header, register_and_login


def test_admin_can_manage_ai_provider_profiles_and_masks_secrets(client):
    admin_token = register_and_login(client, "admin@example.com")
    student_token = register_and_login(client, "student@example.com")

    forbidden = client.get("/admin/ai-providers", headers=auth_header(student_token))
    assert forbidden.status_code == 403

    missing_credentials = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={
            "name": "Broken Yandex",
            "provider": "yandex",
            "is_active": True,
            "credentials": {"api_key": "secret-key"},
        },
    )
    assert missing_credentials.status_code == 422
    assert missing_credentials.json()["detail"] == "Yandex folder ID is required"

    created = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={
            "name": "Yandex production",
            "provider": "yandex",
            "is_active": True,
            "credentials": {
                "folder_id": "folder-123",
                "api_key": "yc-test-secret-key",
            },
            "config": {
                "gpt_model_uri": "gpt://folder-123/custom-model",
                "embed_doc_uri": "emb://folder-123/text-search-doc/latest",
                "embed_query_uri": "emb://folder-123/text-search-query/latest",
            },
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["is_active"] is True
    assert profile["credentials_masked"]["api_key"] == "yc••••-key"
    assert "credentials" not in profile

    updated = client.patch(
        f"/admin/ai-providers/{profile['id']}",
        headers=auth_header(admin_token),
        json={"credentials": {"api_key": "", "iam_token": "iam-secret-token"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["credentials_masked"]["api_key"] == "yc••••-key"
    assert updated.json()["credentials_masked"]["iam_token"] == "ia••••oken"

    readiness = client.get("/readiness/ai")
    assert readiness.status_code == 200
    assert readiness.json()["provider"] == "Yandex AI Studio"
    assert readiness.json()["configured"] is True
    assert readiness.json()["mode"] == "real"


def test_admin_can_activate_openai_compatible_provider(client):
    admin_token = register_and_login(client, "admin@example.com")
    yandex = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={
            "name": "Yandex",
            "provider": "yandex",
            "is_active": True,
            "credentials": {"folder_id": "folder-123", "api_key": "yandex-key"},
        },
    )
    assert yandex.status_code == 201, yandex.text

    openai = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={
            "name": "Compatible gateway",
            "provider": "openai_compatible",
            "credentials": {"api_key": "openai-compatible-secret"},
            "config": {
                "base_url": "https://llm.example.com/v1/",
                "evaluation_model": "custom-chat-model",
                "embedding_model": "custom-embedding-model",
            },
        },
    )
    assert openai.status_code == 201, openai.text

    activated = client.post(f"/admin/ai-providers/{openai.json()['id']}/activate", headers=auth_header(admin_token))
    assert activated.status_code == 200, activated.text
    assert activated.json()["is_active"] is True
    assert activated.json()["config"]["base_url"] == "https://llm.example.com/v1"

    providers = client.get("/admin/ai-providers", headers=auth_header(admin_token))
    assert providers.status_code == 200
    by_id = {item["id"]: item for item in providers.json()}
    assert by_id[openai.json()["id"]]["is_active"] is True
    assert by_id[yandex.json()["id"]]["is_active"] is False

    readiness = client.get("/readiness/ai")
    assert readiness.status_code == 200
    assert readiness.json()["provider"] == "OpenAI-compatible"
    assert readiness.json()["configured"] is True
    assert "Chat Completions" in readiness.json()["capabilities"]


def test_admin_can_activate_local_model_without_api_key(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={
            "name": "Local Ollama",
            "provider": "local",
            "is_active": True,
            "config": {
                "base_url": "http://localhost:11434/v1/",
                "evaluation_model": "llama3.1",
                "embedding_model": "nomic-embed-text",
            },
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["provider"] == "local"
    assert payload["is_active"] is True
    assert payload["credentials_masked"] == {}
    assert payload["config"]["base_url"] == "http://localhost:11434/v1"

    readiness = client.get("/readiness/ai")
    assert readiness.status_code == 200
    assert readiness.json()["provider"] == "Local model"
    assert readiness.json()["configured"] is True
    assert "Local chat model" in readiness.json()["capabilities"]


def test_disabled_ai_provider_cannot_be_activated(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/admin/ai-providers",
        headers=auth_header(admin_token),
        json={"name": "Mock off", "provider": "mock", "is_enabled": False},
    )
    assert created.status_code == 201, created.text

    activated = client.post(f"/admin/ai-providers/{created.json()['id']}/activate", headers=auth_header(admin_token))
    assert activated.status_code == 409
    assert activated.json()["detail"] == "Disabled AI provider cannot be activated"
